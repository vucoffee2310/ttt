mkdir -p public api/bin && \
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o api/bin/yt-dlp && \
chmod +x api/bin/yt-dlp && \
cat <<EOF > public/index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Web App</title>
    <style>
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; line-height: 1.6; padding: 2em; max-width: 800px; margin: auto; color: #333; }
        code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 4px; }
        .success { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Setup Complete!</h1>
    <p>The project structure has been created.</p>
    <p class="success">The <code>yt-dlp</code> binary has been downloaded to <code>api/bin/</code> and made executable.</p>
    <p>This is your main <code>index.html</code> file located in the <code>public</code> directory.</p>
</body>
</html>
EOF
