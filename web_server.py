from flask import Flask, request, jsonify, send_from_directory
import os
import uuid
import time
from config import UPLOAD_DIR, AUTO_DELETE_TIME

app = Flask(__name__)

# In-memory store to map User IDs to their uploaded file paths
# Format: { unique_id: { 'file_path': ..., 'user_id': ... } }
upload_store = {}

@app.route('/health')
def health():
    return "Server is running"

@app.route('/upload/<unique_id>', methods=['POST'])
def upload_file(unique_id):
    """Handle file upload for a specific unique ID."""
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save file with unique name to avoid collisions
    timestamp = int(time.time())
    filename = f"{unique_id}_{timestamp}.mp4"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    file.save(filepath)
    
    # Store reference in memory so Bot knows where the file is
    upload_store[unique_id] = {
        'file_path': filepath,
        'user_id': unique_id, # This links back to Telegram User ID or Session ID
        'filename': filename
    }
    
    return jsonify({"message": "Upload successful", "file_id": unique_id}), 200

def get_file(unique_id):
    """Retrieve file info for the bot."""
    if unique_id in upload_store:
        return upload_store[unique_id]
    return None

def cleanup_old_files():
    """Background task to delete files after AUTO_DELETE_TIME"""
    import asyncio
    async def _cleanup():
        while True:
            await asyncio.sleep(3600) # Check every hour
            current_time = time.time()
            for uid, data in list(upload_store.items()):
                # Note: In a real production app, you'd store creation time. 
                # For simplicity, we assume the bot deletes it after processing or we rely on manual cleanup.
                pass 
    asyncio.create_task(_cleanup())

if __name__ == '__main__':
    from config import HOST, PORT
    app.run(host=HOST, port=PORT)
