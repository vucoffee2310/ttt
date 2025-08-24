import os
import subprocess
import tempfile
import requests
from flask import Flask, request, jsonify

# The Flask app object must be named `app` for Vercel's WSGI server
app = Flask(__name__)

# --- Configuration ---
# Get the Deepgram API key from Vercel's Environment Variables
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
UPLOAD_URL = 'https://manage.deepgram.com/storage/assets'

@app.route('/upload-youtube-audio', methods=['POST'])
def upload_youtube_audio():
    """
    API endpoint to download audio from a YouTube URL and upload it to Deepgram.
    Accepts a JSON body with 'video_url', 'cookies', and 'extractor_args' keys.
    """
    if not DEEPGRAM_API_KEY:
        return jsonify({"error": "DEEPGRAM_API_KEY environment variable not set on the server."}), 500

    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Invalid JSON body."}), 400

    video_url = payload.get('video_url')
    cookies_content = payload.get('cookies')
    extractor_args = payload.get('extractor_args')

    if not all([video_url, cookies_content, extractor_args]):
        return jsonify({
            "error": "Missing required fields. 'video_url', 'cookies', and 'extractor_args' are all required."
        }), 400
    
    # --- IMPORTANT CHANGE: Define the full path to the yt-dlp executable ---
    # `__file__` is the path to the current script (e.g., /var/task/api/index.py)
    # `os.path.dirname` gets the directory of the script (e.g., /var/task/api/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # We then join it with 'bin/yt-dlp' to get the full path to our executable
    yt_dlp_executable = os.path.join(script_dir, 'bin', 'yt-dlp')


    with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.txt', encoding='utf-8') as temp_cookie_file:
        temp_cookie_file.write(cookies_content)
        temp_cookie_file.flush()

        # Build the command using the full path to our executable
        yt_dlp_command = [
            yt_dlp_executable,  # <-- This now points to our downloaded file
            '-f', 'ba',
            '-S', '+abr,+tbr,+size',
            '--http-chunk-size', '10M',
            '--limit-rate', '50M',
            '--cookies', temp_cookie_file.name,
            '--extractor-args', extractor_args,
            '-o', '-',
            video_url
        ]

        try:
            yt_dlp_process = subprocess.Popen(
                yt_dlp_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            headers = {
                'Authorization': f'Token {DEEPGRAM_API_KEY}',
                'Content-Type': 'audio/webm',
                'accept': 'application/json'
            }
            
            response = requests.post(
                UPLOAD_URL,
                headers=headers,
                data=yt_dlp_process.stdout
            )
            
            _, stderr_output = yt_dlp_process.communicate()
            if yt_dlp_process.returncode != 0:
                error_message = stderr_output.decode('utf-8', errors='ignore')
                app.logger.error(f"yt-dlp error: {error_message}")
                return jsonify({"error": "Failed to download audio from YouTube.", "details": error_message}), 500

            response.raise_for_status()
            return jsonify(response.json()), response.status_code

        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Failed to upload data to Deepgram.", "details": str(e)}), 500
        except Exception as e:
            app.logger.error(f"An unexpected error occurred: {e}")
            return jsonify({"error": "An unexpected server error occurred."}), 500

# This is a helpful catch-all route for testing if the API is alive
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == 'upload-youtube-audio':
         return jsonify({"error": "This endpoint requires a POST request."}), 405
    return jsonify({"message": "API is running. Send a POST request to /upload-youtube-audio"}), 200
