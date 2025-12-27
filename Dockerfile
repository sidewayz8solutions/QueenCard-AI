# RunPod Serverless Worker for QueenCard AI
# Supports: SD 1.5 img2img, Wan 2.1 text2video & img2video
#
# Build: docker build -t queencard-worker .
# Push to Docker Hub/GHCR, then deploy on RunPod Serverless

FROM runpod/pytorch:1.0.3-cu1290-torch260-ubuntu2204

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
# HuggingFace cache location (models downloaded at runtime)
ENV HF_HOME=/runpod-volume/cache/huggingface
# Transformers offline mode disabled (we need to download models)
ENV TRANSFORMERS_OFFLINE=0
# Disable tokenizers parallelism warning
ENV TOKENIZERS_PARALLELISM=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create cache and temp directories
RUN mkdir -p /runpod-volume/cache/huggingface \
    && mkdir -p /tmp/loras \
    && mkdir -p /tmp/outputs

# Copy and install Python dependencies first (better layer caching)
COPY worker/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY worker/*.py .

# RunPod handler entrypoint
CMD ["python3", "-u", "worker.py"]
