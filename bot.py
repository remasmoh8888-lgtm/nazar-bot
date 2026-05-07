import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import time
import pytz

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["8202101663:AAH6ZqbN58J9YnpswBX8v_bqqSLL7gKlxWE"]
CHAT_ID = os.environ.get("8202101663", "")

def get_nazar():
    """يسحب موقع مدام نزار بدقة من ملف الـ JSON الخاص بالموقع"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        # القراءة من الـ JSON مباشرة للحصول على أدق تحديث
        resp = requests.get("https://madamnazar.io/data.json", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # استخراج البيانات
        location_name = data.get("name", "Unknown Area")
        img_url = data.get("image", "https://madamnazar.io/assets/img/map.png")
        
        # التأكد من أن رابط الصورة كامل
        if img_url.startswith('/'):
            img_url = f"https://madamnazar.io{img_url}"

        logger.info(f"Fetched: {location_name}")
        return img_url, location_name, "N/A"

    except Exception as e:
        logger.error(f"Error: {e}")
        return "https://madamnazar.io/assets/img/map.png", "Check madamnazar.io", "?"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *مرحباً! أنا بوت مدام نزار* 🔮\n\n"
        "أجيب لك موقع مدام نزار في *Red Dead Online* يومياً\n\n"
        "📌 الأوامر:\n"
        "  /nazar — موقع مدام نزار اليوم\n"
        "  /help  — مساعدة",
        parse_mode="Markdown"
    )

async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location, _ = get_nazar()

    if img_url:
        caption = (
            f"🔮 *موقع مدام نزار اليوم*\n\n"
            f"📍 *المنطقة:* {location}\n\n"
            f"_يتحدث الموقع يومياً الساعة 6:00 صباحاً UTC_"
        )
        await msg.delete()
        await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ فشل في جلب البيانات.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔮 *بوت مدام نزار — مساعدة*\n\n"
        "📌 الأوامر:\n"
        "  /nazar — اعرض الموقع الحالي مع الصورة\n"
        "  /start — رسالة الترحيب\n"
        "  /help  — هذه القائمة",
        parse_mode="Markdown"
    )

async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID: return
    img_url, location, _ = get_nazar()
    if img_url:
        caption = f"🔮 *موقع مدام نزار اليوم*\n\n📍 *المنطقة:* {location}"
        await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", nazar_command))
    app.add_handler(CommandHandler("help", help_command))

    if CHAT_ID:
        app.job_queue.run_daily(daily_auto_send, time=time(6, 5, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
