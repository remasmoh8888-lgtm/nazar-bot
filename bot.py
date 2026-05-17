import re
import time
import base64
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "1003763689916"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
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
    # ── المصدر 1: GitHub API (أكثر موثوقية) ──────────────────
    try:
        resp = requests.get(
            "https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json",
            headers={**HEADERS, "Accept": "application/vnd.github.v3+json"},
            timeout=15
        )
        logger.info(f"GitHub API: {resp.status_code}")
        if resp.status_code == 200:
            content_b64 = resp.json().get("content", "")
            raw = base64.b64decode(content_b64).decode("utf-8").strip()
            logger.info(f"nazar.json raw: {raw[:300]}")
            result = _parse_nazar_json(raw)
            if result[1]:
                return result
    except Exception as e:
        logger.error(f"GitHub API error: {e}")

    # ── المصدر 2: GitHub Pages مباشرة ────────────────────────
    try:
        resp = requests.get(
            "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json",
            headers=HEADERS, timeout=15
        )
        logger.info(f"GitHub Pages: {resp.status_code} | {resp.text[:200]}")
        if resp.status_code == 200:
            result = _parse_nazar_json(resp.text)
            if result[1]:
                return result
    except Exception as e:
        logger.error(f"GitHub Pages error: {e}")

    # ── المصدر 3: madamnazar.io ───────────────────────────────
    return _from_madamnazar()


def _parse_nazar_json(raw):
    """يحلل nazar.json بكل صيغه الممكنة"""
    import json
    try:
        data = json.loads(raw)
        logger.info(f"Parsed JSON type: {type(data)} | value: {data}")

        if isinstance(data, int):
            return _location_from_point(data)

        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, int):
                return _location_from_point(item)
            if isinstance(item, dict):
                point = item.get("point") or item.get("id") or item.get("index")
                if point:
                    return _location_from_point(int(point))
                loc = item.get("location") or item.get("name")
                if loc:
                    img = _get_madamnazar_image()
                    return img, str(loc).title(), item.get("region", "")

        if isinstance(data, dict):
            point = data.get("point") or data.get("id") or data.get("location_id") or data.get("index")
            if point:
                return _location_from_point(int(point))
            loc = data.get("location") or data.get("name")
            if loc:
                img = _get_madamnazar_image()
                return img, str(loc).title(), data.get("region", "")

    except Exception as e:
        logger.error(f"JSON parse error: {e} | raw: {raw[:100]}")
    return None, None, None


def _location_from_point(point):
    if point in LOCATIONS:
        info = LOCATIONS[point]
        img = _get_madamnazar_image()
        logger.info(f"Point {point} → {info['name']}")
        return img, info["name"], info["region"]
    logger.warning(f"Unknown point: {point}")
    return None, None, None


def _get_madamnazar_image():
    for delta in [0, -1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                f"https://madamnazar.io/madam-nazar-location-{date}",
                headers={"User-Agent": HEADERS["User-Agent"], "Cache-Control": "no-cache"},
                timeout=10
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                tag = soup.find("meta", property="og:image")
                if tag and tag.get("content"):
                    logger.info(f"Image from madamnazar [{date}]: {tag.get('content')}")
                    return tag.get("content")
        except Exception as e:
            logger.error(f"Image fetch error: {e}")
    return None


def _from_madamnazar():
    for delta in [0, -1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                f"https://madamnazar.io/madam-nazar-location-{date}",
                headers={"User-Agent": HEADERS["User-Agent"], "Cache-Control": "no-cache"},
                timeout=12
            )
            logger.info(f"madamnazar [{date}]: {resp.status_code}")
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            img_tag = soup.find("meta", property="og:image")
            img_url = img_tag.get("content") if img_tag else None
            desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            desc = desc_tag.get("content", "") if desc_tag else ""
            logger.info(f"madamnazar desc: {desc[:150]}")
            m = re.search(r"point\s*\d+\s*[—\-–]+\s*([^—\-–(]+?)\s*\(([^)]+)\)", desc, re.I)
            if m:
                return img_url, m.group(1).strip().title(), m.group(2).strip().title()
            m2 = re.search(r"point\s*\d+\s*[—\-–]+\s*([^—\-–(.]{3,})", desc, re.I)
            if m2:
                return img_url, m2.group(1).strip().title(), ""
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.warning("Conflict: waiting...")
        time.sleep(3)
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Network: {context.error}")
    else:
        logger.error(f"Error: {context.error}")


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


def main():
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
        
