# ----------------------------
# 🏗 Stage 1: Build environment
# ----------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies (clean layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies in a virtualenv-like folder
RUN pip install --upgrade pip \
    && pip install --user --no-cache-dir -r requirements.txt


# ----------------------------
# 🚀 Stage 2: Runtime environment
# ----------------------------
FROM python:3.11-slim

WORKDIR /app

# Install only pip (no dev tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
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
