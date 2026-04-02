import multiprocessing
import os

# Gunicorn configuration for FastAPI/Uvicorn
bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"

# Path to the application
# Use 'main:app' when running gunicorn -c gunicorn_conf.py main:app
