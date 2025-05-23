#!/bin/bash

# Stop running container named 'videodownloader' (if exists)
docker stop videodownloader 2>/dev/null || true

# Remove any container named 'videodownloader' (running or not)
docker rm videodownloader 2>/dev/null || true

# Build the Docker image
docker build -t videodownloader .

# Run the container
# docker run -d -p 5000:5000 --name videodownloader videodownloader