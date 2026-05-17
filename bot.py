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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Cache-Control": "no-cache",
}

# ─── صورة fallback من ويكي ────────────────────────────────────
FALLBACK_IMG = "https://static.wikia.nocookie.net/reddead/images/5/5e/Madam_Nazar_RDO.png"

# ─── المصدر الأول: rdotracker ─────────────────────────────────
def get_nazar_rdotracker():
    try:
        r = requests.get(
            "https://rdotracker.com/api/nazar",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        spot = (data.get("location") or data.get("name") or "").strip()
        if spot:
            logger.info(f"[rdotracker] Location: {spot}")
            return spot
    except Exception as e:
        logger.warning(f"[rdotracker] failed: {e}")
    return None

# ─── المصدر الثاني: madamnazar.io ─────────────────────────────
def get_nazar_madamnazar():
    try:
        r = requests.get(
            "https://madamnazar.io/api/nazar",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        # جرب كل الحقول الممكنة
        spot = (
            data.get("location") or
            data.get("name") or
            data.get("area") or
            data.get("region") or ""
        ).strip()
        if spot:
            logger.info(f"[madamnazar] Location: {spot}")
            return spot
    except Exception as e:
        logger.warning(f"[madamnazar] failed: {e}")
    return None

# ─── المصدر الثالث: wherenazar.com ────────────────────────────
def get_nazar_wherenazar():
    try:
        r = requests.get(
            "https://wherenazar.com/api/location",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        spot = (data.get("location") or data.get("name") or "").strip()
        if spot:
            logger.info(f"[wherenazar] Location: {spot}")
            return spot
    except Exception as e:
        logger.warning(f"[wherenazar] failed: {e}")
    return None

# ─── المصدر الرابع: coyotejack scraping ───────────────────────
def get_nazar_coyotejack():
    try:
        r = requests.get(
            "https://www.coyotejack.net/where-is-madam-nazar/",
            headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for h2 in soup.find_all("h2"):
            if "Nazar" in h2.get_text():
                p = h2.find_next_sibling("p")
                text = p.get_text(strip=True) if p else ""
                m = re.search(r"(?:near|in) ([A-Z][^,\.]+)", text)
                if m:
                    spot = m.group(1).strip()
                    logger.info(f"[coyotejack] Location: {spot}")
                    return spot
    except Exception as e:
        logger.warning(f"[coyotejack] failed: {e}")
    return None

# ─── جمع كل المصادر ───────────────────────────────────────────
def get_nazar():
    spot = (
        get_nazar_rdotracker() or
        get_nazar_madamnazar() or
        get_nazar_wherenazar() or
        get_nazar_coyotejack()
    )
    if not spot:
        return None, None

    # بناء رابط الصورة
    slug = spot.lower().replace(" ", "-").replace("'", "").replace("ó", "o")
    img_url = f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"

    # تحقق إن الصورة موجودة
    try:
        test = requests.head(img_url, timeout=5)
        if test.status_code != 200:
            img_url = FALLBACK_IMG
    except Exception:
        img_url = FALLBACK_IMG

    return img_url, spot


def get_countdown():
    now = datetime.now(timezone.utc)
    next_change = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= next_change:
        next_change += timedelta(days=1)
    remaining = next_change - now
    hours = int(remaining.total_seconds()) // 3600
    minutes = (int(remaining.total_seconds()) % 3600) // 60
    return hours, minutes


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
    img_url, spot = get_nazar()

    if spot:
        hours, minutes = get_countdown()
        caption = (
            f"📍 *{spot}*\n\n"
            f"⏳ يتغير الموقع بعد: {hours}س {minutes}د"
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
        await msg.edit_text("❌ كل المصادر فشلت، حاول بعد شوي.")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}"
    )


async def text_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_nazar(update, context)


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    img_url, spot = get_nazar()
    if not spot:
        return
    hours, minutes = get_countdown()
    caption = (
        f"📍 *{spot}*\n\n"
        f"⏳ يتغير الموقع بعد: {hours}س {minutes}د"
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


# ─── التشغيل ──────────────────────────────────────────────────
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
