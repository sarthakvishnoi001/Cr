import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters,
    ConversationHandler
)
import ffmpeg
import aiofiles
import uuid

# Import config
from config import BOT_TOKEN, UPLOAD_WEBSITE_LINK, WATERMARK_PATH, UPLOAD_DIR, AUTO_DELETE_TIME, WATERMARK_OPACITY

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# State constants for ConversationHandler
WAITING_FOR_WATERMARK_CHOICE = 1
PROCESSING = 2

def get_unique_filename():
    """Generate a unique filename to avoid conflicts."""
    return f"{uuid.uuid4().hex}.mp4"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and instructions."""
    welcome_text = (
        "👋 Welcome! I can help you remove metadata/copyright info from your video.\n\n"
        "1. Send me the command `/cr` to start.\n"
        "2. Upload your video.\n"
        "3. Choose if you want a watermark.\n"
        "4. Download the result!"
    )
    await update.message.reply_text(welcome_text)

async def start_copyright_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate the copyright removal process."""
    # Step 1: Send website link for upload (as requested)
    caption = (
        "✅ Command received! 🚀\n\n"
        "Please upload your video file here:\n"
        f"🔗 {UPLOAD_WEBSITE_LINK}\n\n"
        "(Or you can send the video directly to me if preferred, but following the prompt above.)"
    )
    
    # Note: Since Telegram bots can't force a web upload flow without an API, 
    # we simulate the "Upload via Link" step. 
    # If you want strict adherence to your prompt, we wait for them to come back or just proceed.
    # For better UX, I will allow them to send the video directly in the next step, 
    # but I will display the link as requested.
    
    await update.message.reply_text(caption)
    
    # Wait for user to send the video file
    # We use ConversationHandler state
    return WAITING_FOR_WATERMARK_CHOICE

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the video file."""
    if update.message.video or update.message.document:
        file_obj = update.message.video.file_id if update.message.video else update.message.document.file_id
        file = await context.bot.get_file(file_obj)
        
        unique_name = get_unique_filename()
        input_path = os.path.join(UPLOAD_DIR, f"input_{unique_name}")
        output_path = os.path.join(UPLOAD_DIR, f"output_{unique_name}.mp4")
        
        # Download the file
        await file.download_to_drive(input_path)
        logger.info(f"Downloaded video to {input_path}")
        
        # Ask about watermark
        keyboard = [
            [InlineKeyboardButton("Yes, add watermark", callback_data='watermark_yes')],
            [InlineKeyboardButton("No watermark", callback_data='watermark_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("Do you want to add a watermark to the video?", reply_markup=reply_markup)
        
        # Store input path in context for later use
        context.user_data['input_path'] = input_path
        context.user_data['output_path'] = output_path
        context.user_data['unique_name'] = unique_name
        
        return WAITING_FOR_WATERMARK_CHOICE
    else:
        await update.message.reply_text("Please send a video or document file.")
        return WAITING_FOR_WATERMARK_CHOICE

async def handle_watermark_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Yes/No watermark choice."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'watermark_yes':
        # Send another link for watermark upload (as per prompt)
        wm_link = "https://yourwebsite.com/upload-watermark" # Placeholder
        await query.edit_message_text(
            f"Great! Upload your custom watermark image here:\n🔗 {wm_link}\n\n"
            "(Or I will use the default centered watermark with 15% opacity.)"
        )
        context.user_data['add_watermark'] = True
        
    elif query.data == 'watermark_no':
        await query.edit_message_text("Okay, no watermark. Processing now...")
        context.user_data['add_watermark'] = False
        
    # Trigger processing after a short delay to allow user to read message
    asyncio.create_task(process_video(update, context))
    
    return PROCESSING

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run ffmpeg to remove metadata and optionally add watermark."""
    input_path = context.user_data['input_path']
    output_path = context.user_data['output_path']
    add_watermark = context.user_data.get('add_watermark', False)
    
    try:
        # 1. Remove Metadata
        # -metadata all removes most metadata fields
        # -c copy avoids re-encoding if no watermark is needed, preserving quality/resolution
        
        cmd = [
            'ffmpeg', '-y', 
            '-i', input_path,
            '-metadata', 'all=',  # Clear all metadata
            '-c:v', 'copy',       # Copy video codec (same resolution/quality)
            '-c:a', 'copy',       # Copy audio codec
        ]
        
        if add_watermark:
            # 2. Add Watermark
            # Filter complex to overlay watermark in center with opacity
            # vf='drawtext=...' or 'overlay' is used. 
            # We use 'overlay' with a simple white box or image for transparency effect.
            
            # Assuming you have a PNG watermark.png with transparency
            # This filter overlays the watermark at 50% width, 50% height (center)
            # opacity=0.15 is handled by ffmpeg's alpha blending if PNG has alpha
            
            vf = f"overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:format=auto,opacity={WATERMARK_OPACITY}"
            
            cmd = [
                'ffmpeg', '-y', 
                '-i', input_path,
                '-i', WATERMARK_PATH,
                '-filter_complex', f"[0:v][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:format=auto,opacity={WATERMARK_OPACITY}[v]",
                '-map', '[v]',
                '-c:a', 'copy',      # Keep audio
                '-metadata', 'all=',
                output_path
            ]
        else:
            # Just metadata removal
            pass

        # Execute FFmpeg
        await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info(f"Processing complete. Output saved to {output_path}")
        
        # Send the processed video
        with open(output_path, 'rb') as video:
            await update.message.reply_video(
                video, 
                caption="✅ Video processed! Metadata removed. Downloading..."
            )
            
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def auto_delete_file(context: ContextTypes.DEFAULT_TYPE, file_path):
    """Delete the file after 1 hour."""
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        os.remove(file_path)
        logger.info(f"Deleted file: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {e}")

async def main():
    # Build the application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handler for /cr
    cr_handler = CommandHandler('cr', start_copyright_removal)
    
    # Add message handler for video (to catch uploads after /cr)
    # Note: In a real scenario, you might want to restrict this to only happen after /cr
    video_handler = MessageHandler(filters.VIDEO | filters.Document(video=["video/mp4"]), handle_video_upload)

    # Callback query handler for watermark choice
    callback_handler = CallbackQueryHandler(handle_watermark_choice)

    # Add handlers
    app.add_handler(cr_handler)
    app.add_handler(video_handler)
    app.add_handler(callback_handler)
    
    # Start polling
    logger.info("Bot is starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Keep the bot running
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    import sys
    from telegram.ext import CallbackQueryHandler
    # Re-import for scope if needed, but usually fine in main
    
    # Note: The above main() function is simplified. 
    # For production, use the standard run_polling() method with ConversationHandler.
