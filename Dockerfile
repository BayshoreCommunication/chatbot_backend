FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip

# Copy requirements and install Python dependencies (using pre-compiled wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=all -r requirements.txt

# Copy only essential application files (excluding venv, logs, etc.)
COPY main.py .
COPY models/ ./models/
COPY routes/ ./routes/
COPY services/ ./services/
COPY utils/ ./utils/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
