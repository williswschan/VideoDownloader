from flask import Flask, render_template, request, send_from_directory, redirect, url_for, abort, Response, stream_with_context
import os
import subprocess
import secrets
from datetime import datetime
import glob
import time
import re
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)

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

# Log all requests
@app.before_request
def log_request_info():
    logger.info('Request: %s %s', request.method, request.url)
    logger.info('Full URL: %s', request.url)
    logger.info('Base URL: %s', request.base_url)
    logger.info('Host URL: %s', request.host_url)
    logger.info('Headers: %s', dict(request.headers))
    logger.info('X-Forwarded-For: %s', request.headers.get('X-Forwarded-For'))
    logger.info('X-Forwarded-Proto: %s', request.headers.get('X-Forwarded-Proto'))
    logger.info('X-Forwarded-Host: %s', request.headers.get('X-Forwarded-Host'))
    logger.info('Host: %s', request.headers.get('Host'))
    logger.info('Referer: %s', request.headers.get('Referer'))
    logger.info('CF-Connecting-IP: %s', request.headers.get('CF-Connecting-IP'))
    logger.info('CF-Ray: %s', request.headers.get('CF-Ray'))
    logger.info('CDN-Loop: %s', request.headers.get('CDN-Loop'))

DOWNLOADS_DIR = os.path.abspath('downloads')
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

@app.route('/', methods=['GET', 'POST'])
def index():
    logger.info('Accessing index page')
    video_files = []
    
    for fname in os.listdir(DOWNLOADS_DIR):
        if fname.lower().endswith((
            '.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov', '.wmv', '.m4a',  # video/audio
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
            video_files.append((dt_str, fname, size_str))
    
    def get_mtime(video_tuple):
        return os.path.getmtime(os.path.join(DOWNLOADS_DIR, video_tuple[1]))
    video_files.sort(key=get_mtime, reverse=True)

    return render_template('index.html', video_files=video_files)

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
    except Exception as e:
        pass
    return redirect(url_for('index'))

@app.route('/stream')
def stream():
    raw_url = request.args.get('url')
    if not raw_url:
        logger.warning('No URL provided in stream request')
        def error_gen():
            yield 'data: No URL provided\n\n'
        return Response(error_gen(), mimetype='text/event-stream')

    # Extract the first URL from the input string
    match = re.search(r'https?://[^\s]+', raw_url)
    url = match.group(0) if match else None

    if not url:
        logger.warning('No valid URL found in input: %s', raw_url)
        def error_gen():
            yield 'data: No valid URL found in input\n\n'
        return Response(error_gen(), mimetype='text/event-stream')

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
        url
    ]

    def generate():
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            logger.info('yt-dlp output: %s', line.rstrip())
            yield f'data: {line.rstrip()}\n\n'
        process.stdout.close()
        process.wait()
        # After download, update the file's mtime to now
        files = glob.glob(os.path.join(DOWNLOADS_DIR, '*'))
        if files:
            latest_file = max(files, key=os.path.getmtime)
            now = time.time()
            os.utime(latest_file, (now, now))

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
    logger.info('Response Headers: %s', dict(response.headers))
    return response

# --------------------------- Main ---------------------------

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False  # Disable debug mode
    ) 