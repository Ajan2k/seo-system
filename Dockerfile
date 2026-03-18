FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files & buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for building C extensions and downloading
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install specific Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directories to ensure permissions are handled early
RUN mkdir -p /app/data /app/logs /app/data/images

# Copy source code (respects .dockerignore)
COPY . .

# Set default env variables
ENV ENVIRONMENT=production
ENV DATABASE_PATH=/app/data/posts.db

# Expose FastAPI port
EXPOSE 8001

# Start server using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
