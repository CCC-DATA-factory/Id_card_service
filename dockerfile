# ----------------------------
# 🏗 Stage 1: Build environment
# ----------------------------
FROM python:3.11-slim AS builder
WORKDIR /app

# Install system dependencies for EasyOCR and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install PyTorch CPU-only FIRST (before other dependencies)
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir \
    torch==2.1.0 torchvision==0.16.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Then install other dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# ----------------------------
# 🚀 Stage 2: Runtime environment
# ----------------------------
FROM python:3.11-slim
WORKDIR /app

# Install runtime dependencies for EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy your app code
COPY ./app ./app
WORKDIR /app/app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]