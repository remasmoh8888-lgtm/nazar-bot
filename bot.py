import re, time, base64, json, logging, requests, sys, threading
from datetime import datetime, timezone, timedelta, time as dtime
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from bs4 import BeautifulSoup
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

POINT_MAP = {
    "1":  ("Grizzlies East",    "Ambarino"),
    "2":  ("Grizzlies East",    "Ambarino"),
    "3":  ("Black Balsam Rise", "Ambarino"),
    "4":  ("Big Valley",        "West Elizabeth"),
    "5":  ("Flatneck Station",  "New Hanover"),
    "6":  ("The Heartlands",    "New Hanover"),
    "7":  ("Bluewater Marsh",   "Lemoyne"),
    "8":  ("Great Plains",      "West Elizabeth"),
    "9":  ("Scarlett Meadows",  "Lemoyne"),
    "10": ("Tumbleweed",        "New Austin"),
    "11": ("Hennigan's Stead",  "New Austin"),
    "12": ("Twin Rocks",        "New Austin"),
}

ID_MAP = {
    "der": ("Bluewater Marsh",   "Lemoyne"),
    "grz": ("Grizzlies East",    "Ambarino"),
    "bbr": ("Black Balsam Rise", "Ambarino"),
    "bgv": ("Big Valley",        "West Elizabeth"),
    "blg": ("Scarlett Meadows",  "Lemoyne"),
    "bwm": ("Bluewater Marsh",   "Lemoyne"),
    "bch": ("Beecher's Hope",    "West Elizabeth"),
    "twn": ("Twin Rocks",        "New Austin"),
    "tmw": ("Tumbleweed",        "New Austin"),
    "flt": ("Flatneck Station",  "New Hanover"),
    "lmp": ("The Heartlands",    "New Hanover"),
    "wnr": ("The Heartlands",    "New Hanover"),
    "ann": ("Grizzlies East",    "Ambarino"),
    "grw": ("Grizzlies East",    "Ambarino"),
}

# ── Cooldown ──────────────────────────────────────────────
_cooldown_lock = threading.Lock()
COOLDOWN: dict = {}

def is_on_cooldown(user_id: int) -> bool:
    now = time.time()
    with _cooldown_lock:
        if user_id in COOLDOWN and now - COOLDOWN[user_id] < 10:
            return True
        COOLDOWN[user_id] = now
    return False

# ── Cache ─────────────────────────────────────────────────
_cache: dict = {"img": None, "location": None, "region": None, "fetched_at": None}

def _cache_valid() -> bool:
    if not _cache["fetched_at"]:
        return False
    now = datetime.now(timezone.utc)
    last_reset = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now.hour < 6:
        last_reset -= timedelta(days=1)
    return _cache["fetched_at"] > last_reset

# ── Fetch من madamnazar.io ────────────────────────────────
def get_nazar():
    # يجرب اليوم وأمس لو الصفحة ما نزلت بعد
    for days_back in [0, 1]:
        target = datetime.now(timezone.utc) - timedelta(days=days_back)
        date_str = target.strftime("%Y-%m-%d")
        url = f"https://madamnazar.io/madam-nazar-location-{date_str}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            logger.info(f"madamnazar.io [{date_str}] status: {resp.status_code}")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # الصورة/الخريطة من madamnazar.io
            img_tag = soup.find("img")
            img_url = img_tag["src"] if img_tag else None

            text = soup.get_text()
            point_match = re.search(r"point (\d+)", text, re.IGNORECASE)
            point = point_match.group(1) if point_match else None

            if point and point in POINT_MAP:
                name, region = POINT_MAP[point]
                logger.info(f"✅ point {point} → {name}, {region} | img: {img_url}")
                return img_url, name, region

        except Exception as e:
            logger.error(f"madamnazar.io error [{date_str}]: {e}")

    # Fallback على jeanropke
    logger.warning("Fallback → jeanropke")
    return _get_nazar_jeanropke()


def _get_nazar_jeanropke():
    sources = [
        ("api",   "https://api.github.com/repos/jeanropke/RDR2CollectorsMap/contents/data/nazar.json"),
        ("pages", "https://jeanropke.github.io/RDR2CollectorsMap/data/nazar.json"),
    ]
    for name, url in sources:
        try:
            headers = {**HEADERS}
            if name == "api":
                headers["Accept"] = "application/vnd.github.v3+json"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            raw = (base64.b64decode(resp.json()["content"]).decode()
                   if name == "api" else resp.text)
            data = json.loads(raw)
            first = data[0] if isinstance(data, list) else data
            loc_id = first.get("id", "").strip().lower()
            logger.info(f"jeanropke loc_id: {loc_id}")
            if loc_id in ID_MAP:
                loc, region = ID_MAP[loc_id]
                return None, loc, region
        except Exception as e:
            logger.error(f"jeanropke [{name}] error: {e}")
    return None, None, None


def get_nazar_cached():
    if _cache_valid():
        logger.info("📦 من الكاش")
        return _cache["img"], _cache["location"], _cache["region"]
    img, location, region = get_nazar()
    if location:
        _cache.update({
            "img": img, "location": location,
            "region": region,
            "fetched_at": datetime.now(timezone.utc)
        })
    return img, location, region

# ── Countdown ─────────────────────────────────────────────
def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60

# ── Watchdog ──────────────────────────────────────────────
def watchdog():
    while True:
        time.sleep(300)
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe",
                timeout=10
            )
            if r.status_code == 200:
                logger.info("💚 Watchdog OK")
            else:
                raise Exception(f"status {r.status_code}")
        except Exception as e:
            logger.error(f"🔴 Watchdog فشل: {e}")
            sys.exit(1)

# ── Handlers ──────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.warning("⚠️ Conflict")
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Network: {context.error}")
    else:
        logger.error(f"Error: {context.error}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو اكتب نزار — لموقع مدام نزار\n\n"
        "🌸 /map — لخريطة الكولكتر التفاعلية\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_on_cooldown(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location, region = get_nazar_cached()

    if not location:
        await msg.edit_text("❌ ما قدرت أجيب الموقع، حاول مرة ثانية.")
        return

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
            logger.error(f"صورة فشلت: {e}")

    await update.message.reply_text(caption, parse_mode="Markdown")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    _cache["fetched_at"] = None
    img_url, location, region = get_nazar_cached()

    if not location:
        return

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

# ── Main ──────────────────────────────────────────────────
def main():
    threading.Thread(target=watchdog, daemon=True).start()
    logger.info("👁️ Watchdog شغال")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"نزار"), send_nazar
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"كول[ي]?كتر"), map_command
    ))
    app.add_error_handler(error_handler)
    app.job_queue.run_daily(
        daily_auto_send, time=dtime(6, 1, 0, tzinfo=pytz.UTC)
    )

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
