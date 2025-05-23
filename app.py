from flask import Flask, render_template, request, send_from_directory, redirect, url_for, abort, Response, stream_with_context, session
import os
import subprocess
import secrets
from datetime import datetime, timedelta
import glob
import time
import re
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True  # Only if using HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Session lasts for 1 day
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'video_downloader_session'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh session on each request

# Configure ProxyFix with all possible headers
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # X-Forwarded-For
    x_proto=1,    # X-Forwarded-Proto
    x_host=1,     # X-Forwarded-Host
    x_port=1,     # X-Forwarded-Port
    x_prefix=1    # X-Forwarded-Prefix
)

# Set the application root URL if behind a proxy
app.config['APPLICATION_ROOT'] = os.environ.get('APPLICATION_ROOT', '/')

# Add Flask-Limiter for rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

DOWNLOADS_DIR = os.path.abspath('downloads')
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

MAGIC_PASSWORD = os.environ.get('MAGIC_PASSWORD')
if not MAGIC_PASSWORD: 
    MAGIC_PASSWORD = 'PASSWORD'

# Get app version from last modified time of app.py
APP_PATH = os.path.abspath(__file__)
try:
    APP_VERSION = os.path.getmtime(APP_PATH)
    APP_VERSION_STR = datetime.fromtimestamp(APP_VERSION).strftime('%Y-%m-%d %H:%M:%S')
except Exception as e:
    APP_VERSION_STR = 'unknown'

# Log the app version once at startup
logger.info(f"App version (last modified): {APP_VERSION_STR}")

@app.before_request
def before_request():
    # Make session permanent for all requests
    session.permanent = True

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("5 per 30 seconds", methods=["POST"])
def index():
    if request.method == 'POST':
        if request.form.get('password') == MAGIC_PASSWORD:
            session['admin_mode'] = True
            session.modified = True # Normally, Flask detects changes to the session, but in some cases (especially with mutable objects), you need to manually mark it as modified.
    
    # Check if admin mode is enabled
    admin_mode = session.get('admin_mode', False)
    video_files = []
    now = time.time()
    
    # Determine which files should be shown in the Downloaded Videos list
    for fname in os.listdir(DOWNLOADS_DIR):
        if fname.lower().endswith((
            '.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov', '.wmv', '.m4a',
            '.mp3', '.aac', '.wav', '.ogg', '.opus', '.flac', '.alac', '.aiff', '.wma', '.amr', '.ac3', '.dsd', '.pcm'
        )):
            fpath = os.path.join(DOWNLOADS_DIR, fname)
            
            mtime = os.path.getmtime(fpath)
            dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            size_bytes = os.path.getsize(fpath)
            if size_bytes >= 1024**3:
                size_str = f"{size_bytes / (1024**3):.2f} GB"
            else:
                size_str = f"{size_bytes / (1024**2):.2f} MB"

            if admin_mode:
                video_files.append((dt_str, fname, size_str))
            else:
                if now - mtime <= 300:
                    video_files.append((dt_str, fname, size_str))

    def get_mtime(video_tuple):
        return os.path.getmtime(os.path.join(DOWNLOADS_DIR, video_tuple[1]))
    
    video_files.sort(key=get_mtime, reverse=True)

    return render_template('index.html', video_files=video_files, admin_mode=admin_mode)

@app.route('/downloads/<path:filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.isfile(file_path):
        abort(404)
    response = send_from_directory(
        DOWNLOADS_DIR, 
        filename, 
        as_attachment=False,
        mimetype='application/octet-stream'
    )
    return response

@app.route('/remove/<path:filename>', methods=['POST'])
def remove_file(filename):
    file_path = os.path.abspath(os.path.join(DOWNLOADS_DIR, filename))

    # Ensure file_path is within DOWNLOADS_DIR
    if not file_path.startswith(DOWNLOADS_DIR):
        logger.warning(f"Attempted directory traversal: {filename}")
        abort(403)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File removed: {filename}")
    except Exception as e:
        logger.error(f"Error removing file: {e}")

    return redirect(url_for('index'))

@app.route('/stream')
def stream():
    # Validate if URL is empty
    raw_url = request.args.get('url')
    if not raw_url:
        def error_gen():
            yield 'data: No valid URL provided\n\n'
        return Response(error_gen(), mimetype='text/event-stream')

    # Extract the first valid URL from the input string
    match = re.search(r'https?://[^\s]+', raw_url)
    url = match.group(0) if match else None

    # Validate if URL is valid
    if not url:
        def error_gen():
            yield 'data: No valid URL provided\n\n'
        return Response(error_gen(), mimetype='text/event-stream')

    def truncate_utf8_bytes(s, max_bytes):
        b = s.encode('utf-8')
        if len(b) <= max_bytes:
            return s
        truncated = b[:max_bytes]
        while True:
            try:
                return truncated.decode('utf-8')
            except UnicodeDecodeError:
                truncated = truncated[:-1]

    def generate():
        try:
            logger.info('Starting download for URL: %s', url)
            if 'douyin' in url:
                ytdlp_path = 'bin/yt-dlp-douyin'
            else:
                ytdlp_path = 'bin/yt-dlp'
            
            # Get intended filename to avoid exceeding 255 bytes in length
            output_template = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
            get_filename_cmd = [
                ytdlp_path,
                '-o', output_template,
                '--get-filename',
                url
            ]
            result = subprocess.run(get_filename_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            filename = result.stdout.strip()
            base, ext = os.path.splitext(filename)
            if len(os.path.basename(filename).encode('utf-8')) > 255:
                max_base_bytes = 255 - len(ext.encode('utf-8'))
                safe_base = truncate_utf8_bytes(base, max_base_bytes)
                safe_filename = safe_base + ext
                output_template = os.path.join(DOWNLOADS_DIR, safe_filename)
                logger.info(f"Filename too long, using truncated filename: {safe_filename}")
                check_filename = safe_filename
            else:
                output_template = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
                check_filename = os.path.basename(filename)

            # Check if file already exists before download
            fpath = os.path.join(DOWNLOADS_DIR, check_filename)
            if os.path.isfile(fpath):
                now = time.time()
                os.utime(fpath, (now, now))
                logger.info(f"File already exists, updated mtime: {fpath}")
                yield f"data: File already downloaded and refreshed: {check_filename}\n\n"
                return

            # Record the set of files before download
            before_files = set(os.listdir(DOWNLOADS_DIR))

            cmd = [
                ytdlp_path,
                '-o', output_template,
                '--no-check-certificate',
                '--ignore-errors',
                '-f', 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]/mp4',
                url
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip()
                logger.info('yt-dlp output: %s', line)
                yield f"data: {line}\n\n"
                
                # Look for the progress line and send progress event
                match_progress = re.search(r'\[download\]\s+(\d+\.\d+)%', line)
                if match_progress:
                    percent = match_progress.group(1)
                    yield f"event: progress\ndata: {percent}\n\n"

            process.stdout.close()
            process.wait()

            # Record the set of files after download
            after_files = set(os.listdir(DOWNLOADS_DIR))
            new_files = after_files - before_files
            if new_files:
                now = time.time()
                for fname in new_files:
                    fpath = os.path.join(DOWNLOADS_DIR, fname)
                    if os.path.isfile(fpath):
                        os.utime(fpath, (now, now))
                        logger.info(f"Set mtime for {fpath} to now after download.")
                        yield f"data: Download completed: {fname}\n\n"
            else:
                yield "data: Download failed\n\n"
                
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}")
            yield f"data: Error: {str(e)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/debug-headers')
def debug_headers():
    info = {
        'headers': dict(request.headers),
        'environ': {
            'wsgi.url_scheme': request.environ.get('wsgi.url_scheme'),
            'REMOTE_ADDR': request.environ.get('REMOTE_ADDR'),
            'HTTP_X_FORWARDED_FOR': request.environ.get('HTTP_X_FORWARDED_FOR'),
            'HTTP_X_FORWARDED_PROTO': request.environ.get('HTTP_X_FORWARDED_PROTO'),
            'HTTP_X_FORWARDED_HOST': request.environ.get('HTTP_X_FORWARDED_HOST'),
            'SERVER_NAME': request.environ.get('SERVER_NAME'),
            'SERVER_PORT': request.environ.get('SERVER_PORT'),
            'REQUEST_METHOD': request.environ.get('REQUEST_METHOD'),
            'PATH_INFO': request.environ.get('PATH_INFO'),
            'SCRIPT_NAME': request.environ.get('SCRIPT_NAME'),
            'QUERY_STRING': request.environ.get('QUERY_STRING'),
        },
        'url': request.url,
        'base_url': request.base_url,
        'host_url': request.host_url,
        'scheme': request.scheme,
        'is_secure': request.is_secure,
    }
    from flask import jsonify
    return jsonify(info)

@app.after_request
def log_response_info(response):
    logger.debug('Response Headers: %s', dict(response.headers))
    return response

@app.route('/lock')
def lock():
    session.pop('admin_mode', None)
    logger.info('Admin Mode: User session has been disabled')
    return redirect(url_for('index'))

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("429.html", error=e), 429

@app.route('/health')
@limiter.exempt
def health():
    return "OK", 200

# --------------------------- Main ---------------------------

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # Disable debug mode
    ) 