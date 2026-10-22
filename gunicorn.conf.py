# gunicorn.conf.py — loaded automatically by gunicorn
import os

# Use $PORT provided by Render (default 10000); fall back to 5000 locally
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# One worker per CPU core; 2 is a safe minimum for Render's free tier
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

# Each worker handles up to 4 simultaneous connections
threads = 4

# Restart workers after 1000 requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Log to stdout so Render captures it
accesslog = "-"
errorlog  = "-"
loglevel  = "info"

# Silence "worker timeout" noise on cold starts
timeout = 120
