import re
import logging
import requests
from datetime import datetime, timezone, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "8202101663"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

# ─── خريطة المواقع للصور ───────────────────────────────────────
LOCATION_IMAGES = {
    "Flat Iron Lake":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-flat-iron-lake.jpg",
    "Big Valley":         "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-big-valley.jpg",
    "West Elizabeth":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-west-elizabeth.jpg",
    "Grizzlies East":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-grizzlies-east.jpg",
    "Grizzlies West":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-grizzlies-west.jpg",
    "Ambarino":           "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-ambarino.jpg",
    "New Hanover":        "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-new-hanover.jpg",
    "Heartlands":         "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-heartlands.jpg",
    "Bluewater Marsh":    "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-bluewater-marsh.jpg",
    "Lemoyne":            "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-lemoyne.jpg",
    "Scarlett Meadows":   "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-scarlett-meadows.jpg",
    "Bayou Nwa":          "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-bayou-nwa.jpg",
    "Roanoke Ridge":      "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-roanoke-ridge.jpg",
    "New Austin":         "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-new-austin.jpg",
    "Cholla Springs":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-cholla-springs.jpg",
    "Gaptooth Ridge":     "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-gaptooth-ridge.jpg",
    "Río Bravo":          "https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-rio-bravo.jpg",
}

# ─── السحب من madamnazar.io ────────────────────────────────────
def get_nazar():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get("https://madamnazar.io/api/nazar", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # البيانات تجي بهالشكل: {"location": "Bluewater Marsh", ...}
        spot = data.get("location") or data.get("name") or ""
        spot = spot.strip()

        if not spot:
            logger.warning(f"Empty location in response: {data}")
            return None, None

        # ابحث عن صورة مطابقة
        img_url = None
        for key, url in LOCATION_IMAGES.items():
            if key.lower() in spot.lower():
                img_url = url
                break

        # fallback: اصنع رابط من الاسم
        if not img_url:
            slug = spot.lower().replace(" ", "-").replace("'", "")
            img_url = f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"

        logger.info(f"Location: {spot} | Image: {img_url}")
        return img_url, spot

    except Exception as e:
        logger.error(f"API error: {e}")
        return None, None


def get_countdown():
    now = datetime.now(timezone.utc)
    next_change = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= next_change:
        next_change += timedelta(days=1)
    remaining = next_change - now
    total_seconds = int(remaining.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes


# ─── الأوامر ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو نزار لارسال موقع نزار.\n\n"
        "🌸 /map : لرابط خريطة الكولكتر التفاعلية.\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, spot = get_nazar()

    if spot:
        caption = f"📍 *{spot}*"
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


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, spot = get_nazar()
    if spot:
        caption = f"📍 *{spot}*"
        if img_url:
            try:
                await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption, parse_mode="Markdown")
                return
            except Exception:
                pass
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode="Markdown")


# ─── التشغيل ───────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), text_nazar))
    app.job_queue.run_daily(daily_auto_send, time=time(6, 10, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
