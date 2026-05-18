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

# ترجمة id من nazar.json إلى اسم قصير + منطقة
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
    """يقصّر الاسم: 'Bolger Glade in southern Scarlet Meadows' → 'Bolger Glade'"""
    if not full_name:
        return full_name
    # نقطع عند " in " أو " near " أو " at "
    for sep in [" in ", " near ", " at ", " - "]:
        if sep in full_name.lower():
            return full_name[:full_name.lower().index(sep)].strip().title()
    return full_name.strip().title()


def _image_url(location_name: str) -> str:
    """يبني رابط الصورة من rdocollector CDN (صور ثابتة دائماً متاحة)"""
    slug = location_name.lower().replace(" ", "-").replace("'", "").replace("'", "")
    return f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"


def get_nazar():
    urls = [
        ("github_api", "https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json"),
        ("github_pages", "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json"),
    ]

    for source, url in urls:
        try:
            headers = {**HEADERS}
            if source == "github_api":
                headers["Accept"] = "application/vnd.github.v3+json"

            resp = requests.get(url, headers=headers, timeout=15)
            logger.info(f"[{source}] {resp.status_code}")

            if resp.status_code != 200:
                continue

            # GitHub API يرجع base64
            if source == "github_api":
                raw = base64.b64decode(resp.json()["content"]).decode("utf-8")
            else:
                raw = resp.text

            logger.info(f"[{source}] raw: {raw[:300]}")
            data = json.loads(raw)

            if not isinstance(data, list) or len(data) == 0:
                logger.warning(f"[{source}] unexpected format")
                continue

            # العنصر الأول = الموقع اليوم
            first = data[0]
            logger.info(f"[{source}] first item: {first}")

            loc_id = first.get("id", "")

            # نجرب ID_MAP أولاً (اسم قصير)
            if loc_id in ID_MAP:
                name, region = ID_MAP[loc_id]
                img = _image_url(name)
                logger.info(f"✅ ID match: {loc_id} → {name}")
                return img, name, region

            # نجرب الحقل "name" من nazar.json
            full_name = (
                first.get("name") or
                first.get("location") or
                first.get("title") or
                ""
            )
            if full_name:
                short = _short_name(full_name)
                img = _image_url(short)
                logger.info(f"✅ Name field: {full_name} → {short}")
                return img, short, ""

            # نجرب الحقل "region"
            region = first.get("region", "")
            if loc_id:
                logger.warning(f"Unknown id: {loc_id} | full item: {first}")
                img = _image_url(loc_id)
                return img, loc_id.upper(), region

        except Exception as e:
            logger.error(f"[{source}] error: {e}")

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
                await update.message.reply_photo(
                    photo=img_url, caption=caption, parse_mode="Markdown"
                )
                return
            except Exception as e:
                logger.error(f"Photo failed ({img_url}): {e}")
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
