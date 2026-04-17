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

def when_ready(server):
    """
    Called just after the server is started. 
    We use this to send a single startup notification via WhatsApp.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        import helpers_v2
        msg = "🚀 ZenETFs: Nowa wersja aplikacji została pomyślnie uruchomiona na serwerze!"
        helpers_v2.notify_success(msg)
    except Exception as e:
        print(f"Failed to send startup notification via Gunicorn hook: {e}")

