import re
import time
import base64
import json
import logging
import requests
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "8202101663"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache",
}

ID_MAP = {
    "der": ("Bluewater Marsh",   "Lemoyne"),
    "grz": ("Grizzlies East",    "Ambarino"),
    "bbr": ("Black Balsam Rise", "Ambarino"),
    "bgv": ("Big Valley",        "West Elizabeth"),
    "blg": ("Bolger Glade",      "Lemoyne"),
    "bwm": ("Bluewater Marsh",   "Lemoyne"),
    "bch": ("Beecher's Hope",    "West Elizabeth"),
    "twn": ("Twin Rocks",        "New Austin"),
    "tmw": ("Tumbleweed",        "New Austin"),
    "flt": ("Flatneck Station",  "New Hanover"),
    "lmp": ("Limpany",           "New Hanover"),
    "wnr": ("Window Rock",       "New Hanover"),
    "ann": ("Annesburg",         "New Hanover"),
    "grw": ("Grizzlies West",    "Ambarino"),
}


def _short_name(full_name: str) -> str:
    """يقصّر: 'Bolger Glade in southern Scarlet Meadows' → 'Bolger Glade'"""
    for sep in [" in ", " near ", " at ", " - "]:
        if sep in full_name.lower():
            return full_name[:full_name.lower().index(sep)].strip().title()
    return full_name.strip().title()


def _image_url(location_name: str) -> str:
    slug = location_name.lower().replace(" ", "-").replace("'", "").replace("'", "")
    return f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"


def get_nazar():
    urls = [
        ("api", "https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json"),
        ("pages", "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json"),
    ]

    for source, url in urls:
        try:
            h = {**HEADERS}
            if source == "api":
                h["Accept"] = "application/vnd.github.v3+json"

            resp = requests.get(url, headers=h, timeout=15)
            logger.info(f"[{source}] {resp.status_code}")
            if resp.status_code != 200:
                continue

            raw = base64.b64decode(resp.json()["content"]).decode("utf-8") if source == "api" else resp.text
            logger.info(f"[{source}] {raw[:400]}")
            data = json.loads(raw)

            if not isinstance(data, list) or not data:
                continue

            first = data[0]
            logger.info(f"First item: {first}")

            # ── اسم الموقع ────────────────────────────────────
            loc_id = first.get("id", "")
            full_name = first.get("name") or first.get("location") or first.get("title") or ""

            if loc_id in ID_MAP:
                name, region = ID_MAP[loc_id]
            elif full_name:
                name = _short_name(full_name)
                region = first.get("region", "")
            else:
                name = loc_id.upper()
                region = ""

            # ── فاست ترافل ───────────────────────────────────
            fast_travel = (
                first.get("nearestFastTravel") or
                first.get("fastTravel") or
                first.get("nearest_fast_travel") or
                first.get("fast_travel") or
                first.get("nearestStation") or
                first.get("station") or
                None
            )

            img = _image_url(name)
            logger.info(f"✅ {name} | FT: {fast_travel} | img: {img}")
            return img, name, region, fast_travel

        except Exception as e:
            logger.error(f"[{source}] error: {e}")

    return None, None, None, None


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
    img_url, location, region, fast_travel = get_nazar()

    if location:
        hours, minutes = get_countdown()
        ft = fast_travel if fast_travel else "غير معروف"

        caption = (
            f"📍 *{location}*\n\n"
            f"أقرب فاست ترفل:\n"
            f"*{ft}*\n\n"
            f"⏳ يتغير بعد: *{hours}س {minutes}د*"
        )

        await msg.delete()
        if img_url:
            try:
                await update.message.reply_photo(
                    photo=img_url, caption=caption, parse_mode="Markdown"
                )
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
    img_url, location, region, fast_travel = get_nazar()
    if location:
        ft = fast_travel if fast_travel else "غير معروف"
        caption = (
            f"📍 *{location}*\n\n"
            f"أقرب فاست ترفل:\n"
            f"*{ft}*\n\n"
            f"⏳ تحدّث الآن 🔄"
        )
        if img_url:
            try:
                await context.bot.send_photo(
                    chat_id=CHAT_ID, photo=img_url,
                    caption=caption, parse_mode="Markdown"
                )
                return
            except Exception:
                pass
        await context.bot.send_message(
            chat_id=CHAT_ID, text=caption, parse_mode="Markdown"
        )


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
