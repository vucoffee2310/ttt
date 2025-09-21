import os
import subprocess
import tempfile
import requests
import threading
from flask import Flask, request, jsonify

# The Flask app object must be named `app` for Vercel's WSGI server
app = Flask(__name__)

# --- Configuration ---
# Get the Deepgram API key from Vercel's Environment Variables
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
UPLOAD_URL = 'https://manage.deepgram.com/storage/assets'

# --- Helper function to log a stream in a separate thread ---
def log_stream(stream, logger):
    """Reads a stream line-by-line and logs it."""
    try:
        # iter(stream.readline, b'') is a non-blocking way to read lines
        for line in iter(stream.readline, b''):
            if line:
                # Decode and strip newline characters before logging
                logger.info(line.decode('utf-8', errors='ignore').strip())
    except Exception as e:
        logger.error(f"Error in log_stream thread: {e}")
    finally:
        stream.close()

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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    yt_dlp_executable = os.path.join(script_dir, 'bin', 'yt-dlp')


    with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.txt', encoding='utf-8') as temp_cookie_file:
        temp_cookie_file.write(cookies_content)
        temp_cookie_file.flush()

        yt_dlp_command = [
            yt_dlp_executable,
            '--progress',
            '--no-warnings',
            '-f', 'ba',
            '-S', '+abr,+tbr,+size',
            '--http-chunk-size', '9M',
            '--limit-rate', '29M',
            '--cookies', temp_cookie_file.name,
            '--extractor-args', extractor_args,
            '-o', '-',
            video_url
        ]

        try:
            # --- MODIFIED: Process handling with threading ---
            app.logger.info(f"Starting yt-dlp with command: {' '.join(yt_dlp_command)}")

            # Start the yt-dlp subprocess
            yt_dlp_process = subprocess.Popen(
                yt_dlp_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Create and start a thread to log stderr (progress updates)
            log_thread = threading.Thread(
                target=log_stream,
                args=(yt_dlp_process.stderr, app.logger)
            )
            log_thread.daemon = True
            log_thread.start()

            headers = {
                'Authorization': f'Token {DEEPGRAM_API_KEY}',
                'Content-Type': 'audio/webm',
                'accept': 'application/json'
            }

            # Stream the audio data directly from yt-dlp's stdout to Deepgram
            response = requests.post(
                UPLOAD_URL,
                headers=headers,
                data=yt_dlp_process.stdout
            )

            # Wait for the yt-dlp process to finish after the upload is complete
            yt_dlp_process.wait()
            # Wait for the logging thread to finish processing any remaining output
            log_thread.join(timeout=2)

            # Check the final return code of the process
            if yt_dlp_process.returncode != 0:
                app.logger.error(f"yt-dlp exited with non-zero code: {yt_dlp_process.returncode}")
                return jsonify({
                    "error": "Failed to download audio from YouTube. Check server logs for details."
                }), 500

            response.raise_for_status()
            return jsonify(response.json()), response.status_code

        except requests.exceptions.RequestException as e:
            app.logger.error(f"Deepgram upload error: {e}")
            return jsonify({"error": "Failed to upload data to Deepgram.", "details": str(e)}), 500
        except Exception as e:
            app.logger.error(f"An unexpected error occurred: {e}")
            return jsonify({"error": "An unexpected server error occurred."}), 500

# --- NEW: Endpoint to get yt-dlp version ---
@app.route('/yt-dlp-version', methods=['GET'])
def get_yt_dlp_version():
    """
    API endpoint to get the version of the bundled yt-dlp executable.
    """
    try:
        # Construct the path to the yt-dlp executable, same as in the upload endpoint
        script_dir = os.path.dirname(os.path.abspath(__file__))
        yt_dlp_executable = os.path.join(script_dir, 'bin', 'yt-dlp')

        # Check if the executable exists before trying to run it
        if not os.path.exists(yt_dlp_executable):
            app.logger.error(f"yt-dlp executable not found at: {yt_dlp_executable}")
            return jsonify({"error": "yt-dlp executable not found on the server."}), 500

        # Run the command to get the version
        version_output = subprocess.check_output(
            [yt_dlp_executable, '--version'],
            text=True  # Get output as a string
        ).strip()

        # The output is just the version string, e.g., "2023.12.30"
        return jsonify({"yt-dlp-version": version_output}), 200

    except FileNotFoundError:
        app.logger.error(f"yt-dlp executable not found at specified path.")
        return jsonify({"error": "yt-dlp executable not found on the server."}), 500
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error getting yt-dlp version. Return code: {e.returncode}, Output: {e.output}")
        return jsonify({
            "error": "Failed to execute yt-dlp to get version.",
            "details": e.output.strip() if e.output else "No output from command."
        }), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred while getting yt-dlp version: {e}")
        return jsonify({"error": "An unexpected server error occurred."}), 500

# This is a helpful catch-all route for testing if the API is alive
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == 'upload-youtube-audio':
         return jsonify({"error": "This endpoint requires a POST request."}), 405
    return jsonify({"message": "API is running. Send a POST request to /upload-youtube-audio or GET /yt-dlp-version"}), 200
