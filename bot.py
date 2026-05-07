import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# إعدادات اللوق
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# التوكن المباشر
TELEGRAM_TOKEN = "8202101663:AAH6ZqbN58J9YnpswBX8v_bqqSLL7gKlxWE"

def get_nazar():
    try:
        # استخدام الرابط المباشر للبيانات اليومية
        api_url = "https://madamnazar.io/data/today.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        resp = requests.get(api_url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            location = data.get("name", "Unknown Area")
            # استخراج الصورة بشكل صحيح
            img = data.get("image", "assets/img/map.png")
            img_url = f"https://madamnazar.io/{img.lstrip('/')}"
            return img_url, location
        return None, None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 هلا بك! أرسل /nazar لمكان مدام نزار.")

async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري جلب الموقع...")
    img_url, location = get_nazar()
    
    if img_url:
        caption = f"🔮 *موقع مدام نزار اليوم*\n\n📍 *المنطقة:* {location}"
        await msg.delete()
        await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ فشل الاتصال بالموقع، جربي مرة ثانية.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", nazar_command))
    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
