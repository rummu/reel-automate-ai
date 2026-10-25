FROM python:3.10-slim

# Install system dependencies (FFmpeg, OpenCV libgl, audio libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set execution permissions for start script
RUN chmod +x start.sh

EXPOSE 5000

# Start both dashboard and background drive watcher
CMD ["./start.sh"]
