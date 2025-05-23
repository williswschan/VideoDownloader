# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y wget ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

# Download the latest official yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o bin/yt-dlp && \
    chmod +x bin/yt-dlp

# Ensure yt-dlp-douyin is executable
RUN chmod +x bin/yt-dlp*

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt

# Create downloads directory
RUN mkdir -p /app/downloads

# Remove __pycache__ directory
RUN rm -rf __pycache__

# Expose port
EXPOSE 5000

# Run the app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app", "--access-logfile", "-", "--timeout", "600"]