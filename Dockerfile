# =============================================================================
# CHAT-PID-AI: 100% Free Ready-to-Deploy Production Image
# =============================================================================
# Includes:
# - AI-powered P&ID analysis
# - Thermodynamic safety auditing with NeqSim
# - HAZOP and engineering validation
#
# Author: CHAT-PID-AI Development Team
# =============================================================================

FROM python:3.11-slim

# Prevent Python from writing pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies:
# 1. OpenCV, EasyOCR, pdf2image dependencies
# 2. Java Runtime Environment (JRE) for NeqSim thermodynamic calculations
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Image processing and PDF utilities
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Java Runtime Environment for NeqSim
    default-jre-headless \
    # Utilities
    curl \
    && rm -rf /var/lib/apt/lists/*

# Verify Java installation for NeqSim
RUN java -version

# Create working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download pre-trained weights for YOLOv8 and EasyOCR to save startup time
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" && \
    python -c "import easyocr; reader = easyocr.Reader(['en'], gpu=False)"

# Copy the entire project into the container
COPY . /app/

# Create runtime directories if they don't exist
RUN mkdir -p uploads exports sample_data static

# Expose FastAPI default port (HuggingFace Spaces uses 7860)
EXPOSE 7860

# Health check for Docker/Kubernetes
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Run FastAPI server via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
