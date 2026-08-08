import asyncio
import os
import logging
import ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from config import BOT_TOKEN, UPLOAD_DIR, WATERMARK_PATH, AUTO_DELETE_TIME

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to hold the web server's base URL (e.g., http://your-ip:5000)
WEB_SERVER_URL = "http://localhost:5000" 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send /cr to remove copyright.")

async def start_copyright_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Generate a UNIQUE ID for this user/session
    unique_id = f"user_{update.effective_user.id}_{int(asyncio.get_event_loop().time())}"
    
    # Construct the unique upload link
    upload_link = f"{WEB_SERVER_URL}/upload/{unique_id}"
    
    # Create an Inline Keyboard with the link
    keyboard = [
        [InlineKeyboardButton("📤 Upload Video Here", url=upload_link)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store unique_id in context so we know which file belongs to this user later
    context.user_data['unique_id'] = unique_id
    
    await update.message.reply_text(
        f"✅ Click below to upload your video.\n\n"
        f"This link is unique to you: {upload_link}\n\n"
        f"(After uploading, the bot will process it automatically.)",
        reply_markup=reply_markup
    )

async def trigger_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called after upload is complete (via Webhook or Polling)"""
    unique_id = context.user_data['unique_id']
    
    # Import here to avoid circular dependency issues if needed
    from web_server import upload_store
    
    file_info = upload_store.get(unique_id)
    if not file_info:
        await update.message.reply_text("❌ File not found. Please try again.")
        return

    input_path = file_info['file_path']
    output_filename = f"processed_{file_info['filename'].replace('.mp4', '')}.mp4"
    output_path = os.path.join(UPLOAD_DIR, output_filename)
    
    await update.message.reply_text("⏳ Processing video... Removing metadata and adding watermark.")

    try:
        # Run FFmpeg
        await asyncio.create_subprocess_exec(
            'ffmpeg', '-y', 
            '-i', input_path,
            '-metadata', 'all=',  # Remove copyright/metadata
            '-c:v', 'copy',       # Keep same resolution/quality
            '-vf', f"overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:opacity={0.15}", # Center watermark
            '-c:a', 'copy',
            output_path
        )
        
        # Send the processed video
        with open(output_path, 'rb') as video:
            await update.message.reply_video(
                video, 
                caption="✅ Done! Metadata removed. Watermark applied."
            )
            
        # Schedule deletion after 1 hour
        asyncio.create_task(delete_file_later(output_path))
        
    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def delete_file_later(file_path):
    """Wait 1 hour then delete the file."""
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        os.remove(file_path)
        logger.info(f"Deleted {file_path}")
    except Exception as e:
        logger.error(f"Error deleting {file_path}: {e}")

def setup_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler('cr', start_copyright_removal))
    # We need a way to trigger processing. 
    # Option A: User clicks link, goes to web page, clicks "Upload", then bot polls for status.
    # Option B (Simpler): Use Webhooks from Flask to Telegram Bot API.
    
    return app
