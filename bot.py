import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import time
import pytz

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN =("8372609971:AAHEmte5MNNL7fOLfYTn3TfBpmfVI4pNppw")
CHAT_ID =("8372609971", "")

COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"


# ─── السحب من rdocollector.com ────────────────────────────────

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
                return img_url, location

        return None, None

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return None, None


def get_countdown():
    """يحسب الوقت الباقي حتى الساعة 6:00 UTC (وقت تغيير مدام نزار)"""
    now = datetime.now(timezone.utc)

    # موعد التغيير القادم الساعة 6:00 UTC
    next_change = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= next_change:
        next_change += timedelta(days=1)

    remaining = next_change - now
    total_seconds = int(remaining.total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    # توقيت الرياض (UTC+3)
    riyadh_change = next_change.astimezone(pytz.timezone("Asia/Riyadh"))
    riyadh_str = riyadh_change.strftime("%I:%M %p")  # 09:00 AM

    return hours, minutes, seconds, riyadh_str


# ─── الأوامر ──────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍/nazar أو نزار لارسال موقع نزار .\n\n"
        "🌸 /map : لرابط خريطة الكولكتر التفاعلية.\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location = get_nazar()

    if location:
        hours, minutes, _, _ = get_countdown()
        caption = (
            f"📍 مكان نزار اليوم\n\n"
            f"*{location}*\n\n"
            f"⏳ يتغير بعد *{hours} ساعة و{minutes} دقيقة*"
        )
        await msg.delete()
        if img_url:
            try:
                await update.message.reply_photo(
                    photo=img_url,
                    caption=caption,
                    parse_mode="Markdown"
                )
                return
            except Exception as e:
                logger.error(f"Photo failed: {e}")
        await update.message.reply_text(caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ ما قدرت أجيب الموقع، حاول مرة ثانية.")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}"
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_nazar(update, context)


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return
    img_url, location = get_nazar()
    if location:
        caption = f"📍 مكان نزار اليوم\n\n*{location}*"
        if img_url:
            try:
                await context.bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=img_url,
                    caption=caption,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=caption,
            parse_mode="Markdown"
        )


# ─── التشغيل ──────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), text_handler))

    if CHAT_ID:
        app.job_queue.run_daily(
            daily_auto_send,
            time=time(6, 10, 0, tzinfo=pytz.UTC)
        )
        logger.info(f"Daily → {CHAT_ID}")

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
