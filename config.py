import os

# Telegram Bot Token
BOT_TOKEN = "7246555679:AAHYqVQcY8T8ozADMzdy6g5seEQ2klfUe5E"

# Web Server Settings
HOST = "0.0.0.0"
PORT = 5000

# Paths
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Watermark Config
WATERMARK_PATH = os.path.join(os.path.dirname(__file__), 'watermark.png') # Create this PNG!
WATERMARK_OPACITY = 0.15  # 15% opacity

# Auto-delete time in seconds (1 hour)
AUTO_DELETE_TIME = 3600
