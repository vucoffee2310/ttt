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

    # --- 1. Get data from client request ---
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

    # --- 2. Use a temporary file for the received cookies ---
    # This is safe for serverless environments as the file is cleaned up automatically
    with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.txt', encoding='utf-8') as temp_cookie_file:
        temp_cookie_file.write(cookies_content)
        temp_cookie_file.flush()  # Ensure content is written to disk before yt-dlp reads it

        # --- 3. Build and run the yt-dlp command with client-provided args ---
        yt_dlp_command = [
            'yt-dlp',
            '-f', 'ba',
            '-S', '+abr,+tbr,+size',
            '--http-chunk-size', '10M',
            '--limit-rate', '50M',
            '--cookies', temp_cookie_file.name,
            '--extractor-args', extractor_args,
            '-o', '-',  # Output to stdout
            video_url
        ]

        try:
            # Start the yt-dlp process to stream the audio
            yt_dlp_process = subprocess.Popen(
                yt_dlp_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # --- 4. Stream the audio to Deepgram ---
            headers = {
                'Authorization': f'Token {DEEPGRAM_API_KEY}',
                'Content-Type': 'audio/webm',
                'accept': 'application/json'
            }

            # The 'data' parameter streams the stdout from the subprocess
            # directly to the POST request, which is highly memory-efficient.
            response = requests.post(
                UPLOAD_URL,
                headers=headers,
                data=yt_dlp_process.stdout
            )

            # Check for errors from the yt-dlp process itself
            _, stderr_output = yt_dlp_process.communicate()
            if yt_dlp_process.returncode != 0:
                error_message = stderr_output.decode('utf-8', errors='ignore')
                app.logger.error(f"yt-dlp error: {error_message}")
                return jsonify({
                    "error": "Failed to download audio from YouTube.",
                    "details": error_message
                }), 500

            # Forward the response from Deepgram to our client
            response.raise_for_status()
            return jsonify(response.json()), response.status_code

        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Failed to upload data to Deepgram.", "details": str(e)}), 500
        except Exception as e:
            app.logger.error(f"An unexpected error occurred: {e}")
            return jsonify({"error": "An unexpected server error occurred."}), 500

# This is a catch-all route that can be useful for Vercel
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return jsonify({"message": "Welcome to the YouTube to Deepgram API. Use the /upload-youtube-audio endpoint."}), 200
