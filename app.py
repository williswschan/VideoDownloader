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
            session.modified = True
            logger.info('Admin Mode: User session enabled via password')
    
    # Debug log for session state
    logger.info(f"Session admin_mode state: {session.get('admin_mode', False)}")
    
    admin_mode = session.get('admin_mode', False)
    video_files = []
    now = time.time()
    
    for fname in os.listdir(DOWNLOADS_DIR):
        if fname.lower().endswith((
            '.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov', '.wmv', '.m4a',
            '.mp3', '.aac', '.wav', '.ogg', '.opus', '.flac', '.alac', '.aiff', '.wma', '.amr', '.ac3', '.dsd', '.pcm'
        )):
            fpath = os.path.join(DOWNLOADS_DIR, fname)
            size_bytes = os.path.getsize(fpath)
            if size_bytes >= 1024**3:
                size_str = f"{size_bytes / (1024**3):.2f} GB"
            else:
                size_str = f"{size_bytes / (1024**2):.2f} MB"
            mtime = os.path.getmtime(fpath)
            dt_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

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
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File removed: {filename}")
    except Exception as e:
        logger.error(f"Error removing file: {e}")
    
    # Set admin mode based on form submission
    if request.form.get('admin_mode') == 'true':
        session['admin_mode'] = True
        session.modified = True
        logger.info("Admin Mode: State preserved after file removal")
    
    return redirect(url_for('index'))

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    if not url:
        return redirect(url_for('index'))
    
    # Clean and encode the URL
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Start the download process
    return redirect(url_for('stream', url=url))

@app.route('/stream')
def stream():
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400

    def generate():
        try:
            logger.info('Starting download for URL: %s', url)
            if 'douyin' in url:
                ytdlp_path = './yt-dlp-douyin'
            else:
                ytdlp_path = './yt-dlp-youtube'
            
            output_template = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
            cmd = [
                ytdlp_path,
                '-o', output_template,
                '--no-check-certificate',
                '--ignore-errors',
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
                url
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            downloaded_file = None
            
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip()
                logger.info('yt-dlp output: %s', line)
                yield f"data: {line}\n\n"
                
                # Look for the destination line
                match = re.search(r'\[download\] Destination: (.+)', line)
                if match:
                    downloaded_file = match.group(1)
            
            process.stdout.close()
            process.wait()
            
            if downloaded_file and os.path.isfile(downloaded_file):
                now = time.time()
                os.utime(downloaded_file, (now, now))
                yield f"data: Download completed: {os.path.basename(downloaded_file)}\n\n"
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

# --------------------------- Main ---------------------------

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # Disable debug mode
    ) 