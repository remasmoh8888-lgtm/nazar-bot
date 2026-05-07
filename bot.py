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
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "")


def get_nazar():
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(
            "https://rdocollector.com/madam-nazar",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        img_tag = soup.find("img", alt="Madam Nazar's current location in Red Dead Online")
        img_url = img_tag["src"] if img_tag else None

        for tag in soup.find_all(["p", "h2", "h3", "div"]):
            text = tag.get_text(strip=True)
            if "Madam Nazar is in" in text:
                match = re.search(r"Madam Nazar is in (.+)", text)
                location = match.group(1).strip() if match else text
                logger.info(f"Location: {location} | Image: {img_url}")
                return img_url, location

        return None, None

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return None, None


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
    img_url, location = get_nazar()

    if location:
        caption = (
            f"🔮 *موقع مدام نزار اليوم*\n\n"
            f"📍 *{location}*\n\n"
            f"_يتحدث يومياً الساعة 6:00 UTC_\n"
            f"_= 9:00 صباحاً بتوقيت الرياض_"
        )
        await msg.delete()
        if img_url:
            try:
                await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
                return
            except Exception as e:
                logger.error(f"Photo failed: {e}")
        await update.message.reply_text(caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ ما قدرت أجيب الموقع، حاول مرة ثانية.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔮 *بوت مدام نزار*\n\n"
        "يسحب الموقع من `rdocollector.com` يومياً\n\n"
        "🕕 *6:00 UTC* = 9:00 صباحاً بالرياض\n\n"
        "/nazar — الموقع الحالي\n"
        "/start — رسالة الترحيب",
        parse_mode="Markdown"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return
    img_url, location = get_nazar()
    if location:
        caption = f"🔮 *موقع مدام نزار اليوم*\n\n📍 *{location}*"
        if img_url:
            try:
                await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption, parse_mode="Markdown")
                return
            except Exception:
                pass
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", nazar_command))
    app.add_handler(CommandHandler("help", help_command))

    if CHAT_ID:
        app.job_queue.run_daily(
            daily_auto_send,
            time=time(6, 10, 0, tzinfo=pytz.UTC)
        )
        logger.info(f"Daily notification → {CHAT_ID}")

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
