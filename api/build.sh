#!/bin/bash

# This script runs during the Vercel build process.

echo "--- Custom Build Script Started ---"

# 1. Install the Python dependencies specified in requirements.txt
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt

# 2. Create a 'bin' directory inside the 'api' folder to store our executable
mkdir -p api/bin

# 3. Download the latest yt-dlp executable directly from GitHub
echo "[2/3] Downloading yt-dlp executable..."
# The -L flag follows redirects to get the latest version
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o api/bin/yt-dlp

# 4. Make the downloaded file executable so our Python script can run it
echo "[3/3] Setting execute permissions on yt-dlp..."
chmod +x api/bin/yt-dlp

echo "--- Custom Build Script Finished Successfully ---"
