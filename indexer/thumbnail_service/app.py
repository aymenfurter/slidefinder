#!/usr/bin/env python3
"""
Thumbnail Generation Microservice

This Flask application provides an API endpoint that:
1. Downloads a PPTX file from a given URL
2. Converts it to PDF using LibreOffice
3. Extracts slide images using pdftoppm
4. Returns the images as a ZIP file or JSON with base64 encoded images

The service processes ONE request at a time to avoid LibreOffice conflicts.
"""

import base64
import hashlib
import io
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lock to ensure only one conversion runs at a time
conversion_lock = threading.Lock()

# Configuration
DOWNLOAD_TIMEOUT = 120  # seconds
CONVERSION_TIMEOUT = 180  # seconds
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
THUMBNAIL_WIDTH = 400  # pixels


def download_pptx(url: str, dest_path: Path) -> bool:
    """Download PPTX file from URL to destination path."""
    try:
        logger.info(f"Downloading PPTX from: {url}")
        response = requests.get(
            url,
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (ThumbnailService/1.0)",
                "Accept": "application/vnd.openxmlformats-officedocument.presentationml.presentation,*/*"
            }
        )
        response.raise_for_status()
        
        # Check content length if available
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_FILE_SIZE:
            logger.error(f"File too large: {content_length} bytes")
            return False
        
        # Write file in chunks
        total_size = 0
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        logger.error(f"File exceeded max size during download")
                        return False
                    f.write(chunk)
        
        logger.info(f"Downloaded {total_size} bytes to {dest_path}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        return False


def convert_pptx_to_thumbnails(pptx_path: Path, output_dir: Path) -> list[Path]:
    """
    Convert PPTX to PNG thumbnails using LibreOffice and pdftoppm.
    
    Returns list of generated thumbnail paths.
    """
    thumbnails = []
    
    try:
        # Step 1: Convert PPTX to PDF using LibreOffice
        logger.info(f"Converting PPTX to PDF: {pptx_path}")
        
        pdf_dir = output_dir / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--invisible",
                "--convert-to", "pdf",
                "--outdir", str(pdf_dir),
                str(pptx_path)
            ],
            capture_output=True,
            timeout=CONVERSION_TIMEOUT,
            text=True,
            env={**os.environ, "HOME": "/tmp"}  # LibreOffice needs HOME
        )
        
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            return thumbnails
        
        # Find the generated PDF
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error("No PDF file generated")
            return thumbnails
        
        pdf_path = pdf_files[0]
        logger.info(f"PDF created: {pdf_path}")
        
        # Step 2: Convert PDF pages to PNG using pdftoppm
        logger.info("Extracting slide images from PDF")
        
        img_dir = output_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        output_prefix = img_dir / "slide"
        
        result = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-scale-to", str(THUMBNAIL_WIDTH),
                str(pdf_path),
                str(output_prefix)
            ],
            capture_output=True,
            timeout=120,
            text=True
        )
        
        if result.returncode != 0:
            logger.warning(f"pdftoppm warning: {result.stderr}")
        
        # Collect generated thumbnails (pdftoppm names them slide-01.png, slide-02.png, etc.)
        for png_file in sorted(img_dir.glob("slide-*.png")):
            thumbnails.append(png_file)
        
        logger.info(f"Generated {len(thumbnails)} thumbnails")
        
    except subprocess.TimeoutExpired:
        logger.error("Conversion timed out")
    except Exception as e:
        logger.error(f"Conversion error: {e}")
    
    return thumbnails


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "thumbnail-generator",
        "timestamp": time.time()
    })


@app.route('/generate', methods=['POST'])
def generate_thumbnails():
    """
    Generate thumbnails from a PPTX URL.
    
    Request JSON:
    {
        "url": "https://example.com/presentation.pptx",
        "session_code": "BRK123",  # Optional: for naming
        "format": "json"  # or "zip"
    }
    
    Response (JSON format):
    {
        "success": true,
        "session_code": "BRK123",
        "slide_count": 10,
        "thumbnails": [
            {"slide_number": 1, "image_base64": "..."},
            ...
        ]
    }
    """
    
    # Parse request
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    
    url = data.get('url')
    if not url:
        return jsonify({"error": "url field required"}), 400
    
    session_code = data.get('session_code', 'unknown')
    output_format = data.get('format', 'json')
    
    logger.info(f"Processing request for session: {session_code}, URL: {url[:100]}...")
    
    # Acquire lock - only one conversion at a time
    if not conversion_lock.acquire(timeout=5):
        return jsonify({
            "error": "Service busy, please retry",
            "retry_after": 5
        }), 503
    
    try:
        # Create temporary directory for this request
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Download PPTX
            pptx_path = tmpdir / f"{session_code}.pptx"
            if not download_pptx(url, pptx_path):
                return jsonify({
                    "error": "Failed to download PPTX",
                    "session_code": session_code
                }), 400
            
            # Verify file is valid
            if not pptx_path.exists() or pptx_path.stat().st_size < 1000:
                return jsonify({
                    "error": "Downloaded file is invalid or too small",
                    "session_code": session_code
                }), 400
            
            # Convert to thumbnails
            output_dir = tmpdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            thumbnails = convert_pptx_to_thumbnails(pptx_path, output_dir)
            
            if not thumbnails:
                return jsonify({
                    "error": "Failed to generate thumbnails",
                    "session_code": session_code
                }), 500
            
            # Return response based on format
            if output_format == 'zip':
                # Create ZIP file with all thumbnails
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for i, thumb_path in enumerate(thumbnails, 1):
                        zf.write(thumb_path, f"{session_code}_{i}.png")
                
                zip_buffer.seek(0)
                return send_file(
                    zip_buffer,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f"{session_code}_thumbnails.zip"
                )
            
            else:  # JSON format with base64
                result = {
                    "success": True,
                    "session_code": session_code,
                    "slide_count": len(thumbnails),
                    "thumbnails": []
                }
                
                for i, thumb_path in enumerate(thumbnails, 1):
                    with open(thumb_path, 'rb') as f:
                        img_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    result["thumbnails"].append({
                        "slide_number": i,
                        "image_base64": img_data
                    })
                
                return jsonify(result)
    
    except Exception as e:
        logger.exception(f"Unexpected error processing {session_code}")
        return jsonify({
            "error": str(e),
            "session_code": session_code
        }), 500
    
    finally:
        conversion_lock.release()


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with service info."""
    return jsonify({
        "service": "SlideFinder Thumbnail Generator",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate": "Generate thumbnails from PPTX URL",
            "GET /health": "Health check"
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Thumbnail Service on port {port}")
    
    # Use Gunicorn in production, Flask dev server for debugging
    if os.environ.get('FLASK_DEBUG'):
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        # Simple Flask server for container (Gunicorn can be used in production)
        app.run(host='0.0.0.0', port=port, threaded=False)
