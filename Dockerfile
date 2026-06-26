# Build pid_ai 100% Free Ready-to-Deploy Production Image
FROM python:3.11-slim

# Prevent Python from writing pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for OpenCV, EasyOCR, and pdf2image (poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

# Expose FastAPI default port
EXPOSE 8000

# Run FastAPI server via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
