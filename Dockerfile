# =============================================================================
# SlideFinder - Dockerfile
# Multi-stage build for optimized container image
# =============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================================================
# Production stage
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (for python-pptx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/ppts data/thumbnails data/compiled_decks data/slide_index data/temp_ppts

# Expose port
EXPOSE 7004

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=7004
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7004/health')" || exit 1

# Run the application from src module
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7004"]
