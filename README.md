# VideoDownloader

**VideoDownloader** is a Python-based web application for downloading videos and audio from a variety of sources. It features a modern web interface, live download progress, admin controls, and is designed for easy deployment with Docker and Kubernetes.

---

## Features

- **Web Interface:** User-friendly UI for submitting download links and managing files.
- **Live Progress:** Real-time download logs and progress bar.
- **Admin Mode:** Unlocks full file management with a password.
- **Rate Limiting:** Prevents abuse with configurable request limits.
- **Health Check Endpoint:** For monitoring and automation.
- **Audio/Video Support:** Downloads in popular formats (mp4, mkv, mp3, etc.).
- **Dockerized:** Simple container deployment.

---

## Project Structure

- `app.py` — Main Flask application
- `requirements.txt` — Python dependencies
- `Dockerfile` — Container build instructions
- `bin/` — Download tools (e.g., yt-dlp)
- `templates/` — HTML templates for the web UI
- `k8s/` — Kubernetes manifests and helper scripts
- `Jenkinsfile` — Jenkins pipeline for CI/CD
- `push_to_registry.sh` — Script to push Docker images to a registry
- `redeploy.sh` — Script to redeploy the application

---

## Getting Started

### Installation (Local)

1. **Clone the repository:**
    ```bash
    git clone https://github.com/williswschan/VideoDownloader.git
    cd VideoDownloader
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Set environment variables (optional but recommended):**
    - `MAGIC_PASSWORD`: Admin password for the web interface

4. **Run the application:**
    ```bash
    python app.py
    ```

### Docker

To build and run with Docker:
```bash
docker run -e MAGIC_PASSWORD=yourpassword -p 5000:5000 videodownloader
``` 

The app will be available at `http://localhost:5000`

---

## Environment Variables

| Variable           | Description                        | Default      |
|--------------------|------------------------------------|--------------|
| `MAGIC_PASSWORD`   | Admin password for web interface   | PASSWORD     |

---

## Example Usage

1. Open the web interface in your browser.
2. Enter the admin password to unlock full features.
3. Paste a video or audio URL and start the download.
4. Monitor progress in real time and manage downloaded files.

---

## Commit Message Types

```
Types:
- feat:      New feature
- fix:       Bug fix
- docs:      Documentation only changes
- style:     Formatting, missing semi colons, etc.
- refactor:  Code change that neither fixes a bug nor adds a feature
- perf:      Performance improvement
- test:      Adding or fixing tests
- chore:     Maintenance

Examples:
- feat: add download progress bar
- fix: correct modify date issue
- docs: update README usage instructions
- refactor: improve file handling logic
- chore: update dependencies
```

---

## Contributing

Contributions are welcome! Please open issues or submit pull requests for improvements.

---

## License

This project is licensed under the MIT License. 
