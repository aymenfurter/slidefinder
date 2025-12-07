# Thumbnail Generation Microservice
# Converts PPTX files to PNG thumbnails using LibreOffice
FROM python:3.11-slim

# Install LibreOffice and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-impress \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create temp directories
RUN mkdir -p /tmp/pptx /tmp/thumbnails

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "app.py"]
