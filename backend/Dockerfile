# Multi-stage / minimal production Dockerfile for LifeNavigator-AI Backend
FROM python:3.11-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user and group for security
RUN groupadd -r -g 1000 appgroup && \
    useradd -r -u 1000 -g appgroup -m -s /bin/bash appuser

# Install pinned Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . /app

# Ensure non-privileged user owns application files
RUN chown -R appuser:appgroup /app

# Switch to non-root execution
USER appuser

EXPOSE 8000

# Backend container readiness healthcheck testing database connectivity
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready').getcode() == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
