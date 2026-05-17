import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.error import Conflict, NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "1003763689916"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache",
}

LOCATIONS = {
    1:  {"name": "Beecher's Hope",   "region": "West Elizabeth"},
    2:  {"name": "Twin Rocks",        "region": "New Austin"},
    3:  {"name": "Window Rock",       "region": "New Hanover"},
    4:  {"name": "Manteca Falls",     "region": "Flat Iron Lake"},
    5:  {"name": "Black Balsam Rise", "region": "Ambarino"},
    6:  {"name": "Grizzlies East",    "region": "Ambarino"},
    7:  {"name": "Bluewater Marsh",   "region": "Lemoyne"},
    8:  {"name": "Bolger Glade",      "region": "Lemoyne"},
    9:  {"name": "Hanging Dog Ranch", "region": "West Elizabeth"},
    10: {"name": "Flatneck Station",  "region": "New Hanover"},
    11: {"name": "Limpany",           "region": "New Hanover"},
    12: {"name": "Benedict Point",    "region": "New Austin"},
}


def get_nazar():
    # نجرب jeanropke nazar.json أولاً
    for url in [
        "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json",
        "https://raw.githubusercontent.com/jeanropke/RDR2CollectorsMap/master/data/nazar.json",
    ]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            logger.info(f"nazar.json → {resp.status_code} | {resp.text[:200]}")
            if resp.status_code == 200:
                data = resp.json()
                point = None
                if isinstance(data, int):
                    point = data
                elif isinstance(data, dict):
                    point = data.get("point") or data.get("id") or data.get("location_id")
                    if not point and "location" in data:
                        img = _get_image()
                        return img, str(data["location"]).title(), str(data.get("region","")).title()
                if point and int(point) in LOCATIONS:
                    info = LOCATIONS[int(point)]
                    img = _get_image()
                    return img, info["name"], info["region"]
        except Exception as e:
            logger.error(f"nazar.json error: {e}")

    # fallback: madamnazar.io
    return _from_madamnazar()


def _get_image():
    for delta in [0, -1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                f"https://madamnazar.io/madam-nazar-location-{date}",
                headers=HEADERS, timeout=10
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                tag = soup.find("meta", property="og:image")
                if tag and tag.get("content"):
                    return tag.get("content")
        except Exception:
            pass
    return None


def _from_madamnazar():
    for delta in [0, -1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                f"https://madamnazar.io/madam-nazar-location-{date}",
                headers=HEADERS, timeout=12
            )
            logger.info(f"madamnazar [{date}] → {resp.status_code}")
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            img_tag = soup.find("meta", property="og:image")
            img_url = img_tag.get("content") if img_tag else None
            desc_tag = soup.find("meta", property="og:description")
            desc = desc_tag.get("content", "") if desc_tag else ""
            logger.info(f"desc: {desc[:100]}")
            m = re.search(r"point\s*\d+\s*[—\-–]+\s*([^—\-–(]+?)\s*\(([^)]+)\)", desc, re.I)
            if m:
                return img_url, m.group(1).strip().title(), m.group(2).strip().title()
        except Exception as e:
            logger.error(f"madamnazar error: {e}")
    return None, None, None


def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60


# ─── Error Handler ────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, Conflict):
        logger.warning("Conflict: another instance running, waiting...")
        time.sleep(5)
    elif isinstance(error, NetworkError):
        logger.warning(f"Network error: {error}")
    else:
        logger.error(f"Error: {error}")


# ─── الأوامر ──────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو نزار لارسال موقع نزار.\n\n"
        "🌸 /map : لرابط خريطة الكولكتر التفاعلية.\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location, region = get_nazar()

    if location:
        hours, minutes = get_countdown()
        caption = f"📍 *{location}*"
        if region:
            caption += f"\n_{region}_"
        caption += f"\n\n⏳ يتغير بعد *{hours} ساعة و{minutes} دقيقة*"
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


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}")


async def text_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_nazar(update, context)


async def text_collector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await map_command(update, context)


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, location, region = get_nazar()
    if location:
        caption = f"📍 *{location}*"
        if region:
            caption += f"\n_{region}_"
        if img_url:
            try:
                await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption, parse_mode="Markdown")
                return
            except Exception:
                pass
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")


# ─── التشغيل ──────────────────────────────────────────────────

def main():
    # انتظار بسيط عشان Railway يوقف النسخة القديمة أولاً
    logger.info("Waiting 5s for old instance to stop...")
    time.sleep(5)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), text_nazar))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"كول[ي]?كتر"), text_collector))
    app.add_error_handler(error_handler)

    app.job_queue.run_daily(daily_auto_send, time=dtime(6, 1, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
                    
