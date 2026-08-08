import asyncio
import json
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder
from config import BOT_TOKEN, UPLOAD_DIR, HOST, PORT
from web_server import app as flask_app, upload_store
import requests  # To call Telegram Bot API

# --- Telegram Bot Setup ---
bot_token = 7246555679:AAHYqVQcY8T8ozADMzdy6g5seEQ2klfUe5E
base_url = f"https://api.telegram.org/bot{bot_token}"

async def send_message(chat_id, text):
    """Helper to send messages via Telegram API"""
    url = f"{base_url}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    # Use requests for simplicity in this single-file script
    # In production, use aiohttp or the bot's internal client
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending msg: {e}")

# --- Webhook Handler for Flask ---
@app.route('/webhook/upload', methods=['POST'])
def handle_webhook():
    """Called by the web page after upload to notify the bot."""
    data = request.json
    unique_id = data.get('unique_id')
    
    if not unique_id:
        return jsonify({"error": "No ID"}), 400
    
    file_info = upload_store.get(unique_id)
    if not file_info:
        return jsonify({"error": "File not found"}), 404
        
    # Trigger processing logic here
    # We need to find the Telegram Chat ID associated with this unique_id
    # For simplicity, let's assume we stored chat_id in upload_store during /cr command
    
    chat_id = file_info.get('chat_id')
    
    if chat_id:
        asyncio.create_task(process_and_send(chat_id, file_info['file_path']))
        
    return jsonify({"status": "processing"})

async def process_and_send(chat_id, input_path):
    """Background task to process video and send it."""
    import ffmpeg
    
    output_filename = f"processed_{os.path.basename(input_path)}.mp4"
    output_path = os.path.join(UPLOAD_DIR, output_filename)
    
    # 1. Remove Metadata & Add Watermark
    await asyncio.create_subprocess_exec(
        'ffmpeg', '-y', 
        '-i', input_path,
        '-metadata', 'all=', 
        '-c:v', 'copy', 
        '-vf', f"overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:opacity=0.15", # Center watermark
        '-c:a', 'copy',
        output_path
    )
    
    # 2. Send to User
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    with open(output_path, 'rb') as video:
        files = {'video': (output_filename, video, 'video/mp4')}
        data = {'chat_id': chat_id}
        requests.post(url, files=files, data=data)
        
    # 3. Schedule Deletion
    asyncio.create_task(delete_file_later(output_path))

async def delete_file_later(file_path):
    import time
    await asyncio.sleep(3600) # 1 hour
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Delete error: {e}")

# --- Main Execution ---
if __name__ == '__main__':
    import threading
    
    def run_flask():
        flask_app.run(host=HOST, port=PORT, debug=False)
        
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    print(f"Web Server running on http://localhost:{PORT}")
    print("Telegram Bot is listening...")
    
    # Keep main thread alive
    while True:
        time.sleep(1)
