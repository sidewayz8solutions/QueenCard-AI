# Use RunPod's PyTorch image - has CUDA, PyTorch, and common ML libs pre-installed
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/cache/huggingface

# Install ffmpeg for video processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create cache directories
RUN mkdir -p /app/cache/huggingface
RUN mkdir -p /tmp/loras

# Install worker requirements
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY worker/ .

CMD ["python3", "-u", "worker.py"]
