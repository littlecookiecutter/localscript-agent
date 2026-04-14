FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Lua syntax checking (optional but recommended)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    lua5.4 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set Python path for imports
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]