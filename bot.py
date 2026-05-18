import re
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pytz

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "8202101663"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

LOCATIONS = {
    "grizzlies east":   ("Annesburg",       "grizzlies-east"),
    "grizzlies west":   ("Strawberry",      "grizzlies-west"),
    "big valley":       ("Strawberry",      "big-valley"),
    "tall trees":       ("Strawberry",      "big-valley"),
    "west elizabeth":   ("Blackwater",      "west-elizabeth"),
    "great plains":     ("Blackwater",      "west-elizabeth"),
    "flat iron lake":   ("Thieves Landing", "flat-iron-lake"),
    "new hanover":      ("Valentine",       "new-hanover"),
    "heartlands":       ("Valentine",       "heartlands"),
    "bluewater marsh":  ("Saint Denis",     "bluewater-marsh"),
    "lemoyne":          ("Rhodes",          "lemoyne"),
    "scarlett meadows": ("Rhodes",          "scarlett-meadows"),
    "scarlet meadows":  ("Rhodes",          "scarlett-meadows"),
    "bolger glade":     ("Rhodes",          "scarlett-meadows"),
    "bayou nwa":        ("Saint Denis",     "bayou-nwa"),
    "roanoke ridge":    ("Annesburg",       "roanoke-ridge"),
    "new austin":       ("Armadillo",       "new-austin"),
    "cholla springs":   ("Armadillo",       "cholla-springs"),
    "gaptooth ridge":   ("Tumbleweed",      "gaptooth-ridge"),
    "rio bravo":        ("Tumbleweed",      "rio-bravo"),
    "ambarino":         ("Colter",          "ambarino"),
    "o'creagh":         ("Annesburg",       "grizzlies-east"),
    "brandywine":       ("Annesburg",       "roanoke-ridge"),
    "cumberland":       ("Valentine",       "new-hanover"),
    "rio del lobo":     ("Tumbleweed",      "rio-bravo"),
}


def get_nazar():
    try:
        ts = int(datetime.now(timezone.utc).timestamp())
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        resp = requests.get(
            f"https://www.coyotejack.net/where-is-madam-nazar/?t={ts}",
            headers=headers, timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for h2 in soup.find_all("h2"):
            if "Where is Madam Nazar Today?" in h2.get_text():
                p = h2.find_next_sibling("p")
                full_text = p.get_text(strip=True) if p else ""
                logger.info(f"Raw: {full_text}")

                spot_match = re.search(r"She is (?:near|in) (.+?)\.", full_text)
                spot = spot_match.group(1).strip() if spot_match else ""

                if not spot:
                    return None, None, None

                nearest = "غير معروف"
                img_url = "https://static.wikia.nocookie.net/reddead/images/5/5e/Madam_Nazar_RDO.png"

                for key, (city, slug) in LOCATIONS.items():
                    if key in spot.lower():
                        nearest = city
                        img_url = f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"
                        break

                logger.info(f"Spot: {spot} | Nearest: {nearest}")
                return img_url, spot, nearest

        return None, None, None

    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None, None


def get_countdown():
    now = datetime.now(timezone.utc)
    next_change = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= next_change:
        next_change += timedelta(days=1)
    remaining = next_change - now
    hours = int(remaining.total_seconds()) // 3600
    minutes = (int(remaining.total_seconds()) % 3600) // 60
    return hours, minutes


def build_caption(spot, nearest, hours, minutes):
    return (
        f"📍 {spot}\n"
        f"━━━━━━━━━━━━\n"
        f"🏙️ أقرب فاست ترفل: {nearest}\n"
        f"━━━━━━━━━━━━\n"
        f"⏳ يتغير بعد: {hours}س {minutes}د"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو نزار لارسال موقع نزار.\n\n"
        "🌸 /map : لرابط خريطة الكولكتر التفاعلية.\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, spot, nearest = get_nazar()

    if spot:
        hours, minutes = get_countdown()
        caption = build_caption(spot, nearest, hours, minutes)
        await msg.delete()
        try:
            await update.message.reply_photo(photo=img_url, caption=caption)
        except Exception as e:
            logger.error(f"Photo failed: {e}")
            await update.message.reply_text(caption)
    else:
        await msg.edit_text("❌ ما قدرت أجيب الموقع، حاول مرة ثانية.")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}")


async def text_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_nazar(update, context)


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, spot, nearest = get_nazar()
    if not spot:
        return
    hours, minutes = get_countdown()
    caption = build_caption(spot, nearest, hours, minutes)
    try:
        await context.bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=caption)
    except Exception:
        await context.bot.send_message(chat_id=CHAT_ID, text=caption)


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
