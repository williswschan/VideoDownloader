# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y wget ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose port
EXPOSE 5000

# Run the app
CMD ["python", "app.py"] 