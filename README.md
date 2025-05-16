# VideoDownloader

VideoDownloader is a Python-based application designed to help users download videos efficiently. The project is containerized with Docker for easy deployment and includes scripts for pushing images to a registry and redeploying the application.

## Features

- Download videos from supported sources
- (Likely) Web interface, based on the presence of `templates/`
- Dockerized for easy deployment
- Simple deployment and redeployment scripts

## Project Structure

- `app.py` — Main application logic (likely includes the web server and download logic)
- `requirements.txt` — Python dependencies
- `Dockerfile` — Containerization instructions
- `bin/` — Binaries
- `templates/` — HTML templates for the web interface
- `push_to_registry.sh` — Script to push Docker images to a registry
- `redeploy.sh` — Script to redeploy the application

## Getting Started

### Prerequisites

- Python 3.8+
- Docker (for containerized deployment)

### Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/williswschan/VideoDownloader.git
    cd VideoDownloader
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Run the application:
    ```bash
    python app.py
    ```

### Docker

To build and run with Docker:
```bash
docker build -t videodownloader .
docker run -p 8080:8080 videodownloader
```

### Deployment

- Use `push_to_registry.sh` to push the Docker image to your registry.
- Use `redeploy.sh` to redeploy the application.

## Contributing

Contributions are welcome! Please open issues or submit pull requests for improvements.

## License

This project is licensed under the MIT License. 