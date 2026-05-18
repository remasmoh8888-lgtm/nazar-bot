import time, base64, json, logging, requests, sys, threading
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
    "der": ("Dewberry Creek",    "Lemoyne"),
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

# ── Cooldown ──────────────────────────────────────────────────────────────────
COOLDOWN: dict = {}

def is_on_cooldown(user_id: int) -> bool:
    now = time.time()
    if user_id in COOLDOWN and now - COOLDOWN[user_id] < 5:
        return True
    COOLDOWN[user_id] = now
    return False

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {"img": None, "location": None, "region": None, "fetched_at": None}

def _cache_valid() -> bool:
    if not _cache["fetched_at"]:
        return False
    now = datetime.now(timezone.utc)
    last_reset = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now.hour < 6:
        last_reset -= timedelta(days=1)
    return _cache["fetched_at"] > last_reset

# ── Image ─────────────────────────────────────────────────────────────────────
def _get_image(location_name: str):
    slug = (location_name.lower()
            .replace(" ", "-")
            .replace("'", "")
            .replace("'", ""))
    url = f"https://rdocollector.nyc3.digitaloceanspaces.com/img/madam-nazar-{slug}.jpg"
    try:
        r = requests.head(url, timeout=5)
        if r.status_code == 200:
            return url
    except Exception:
        pass
    return None

# ── Short Name ────────────────────────────────────────────────────────────────
def _short_name(full_name: str) -> str:
    for sep in [" in ", " near ", " at ", " - "]:
        idx = full_name.lower().find(sep)
        if idx != -1:
            return full_name[:idx].strip().title()
    return full_name.strip().title()

# ── Fetch Nazar ───────────────────────────────────────────────────────────────
def get_nazar():
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

            logger.info(f"✅ loc_id: '{loc_id}' | full: {first}")

            if loc_id in ID_MAP:
                loc, region = ID_MAP[loc_id]
                return _get_image(loc), loc, region

            full = (first.get("name") or first.get("location") or
                    first.get("title") or "")
            if full:
                short = _short_name(full)
                return _get_image(short), short, first.get("region", "")

            if loc_id:
                return _get_image(loc_id), loc_id.upper(), first.get("region", "")

        except Exception as e:
            logger.error(f"[{name}] {e}")

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

# ── Countdown ─────────────────────────────────────────────────────────────────
def get_countdown():
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= nxt:
        nxt += timedelta(days=1)
    total = int((nxt - now).total_seconds())
    return total // 3600, (total % 3600) // 60

# ── Watchdog ──────────────────────────────────────────────────────────────────
def watchdog():
    while True:
        time.sleep(300)  # كل 5 دقائق
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
            logger.error(f"🔴 Watchdog فشل: {e} — إعادة تشغيل...")
            sys.exit(1)  # Railway يعيد التشغيل تلقائي

# ── Handlers ──────────────────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.warning("⚠️ Conflict — نسختين شغالتين!")
    elif isinstance(context.error, NetworkError):
        logger.warning(f"🌐 Network: {context.error}")
    else:
        logger.error(f"❌ Error: {context.error}")


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
            logger.error(f"🖼️ صورة فشلت: {e}")

    await update.message.reply_text(caption, parse_mode="Markdown")


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🌸 خريطة الكولكتر التفاعلية:\n\n{COLLECTORS_MAP}"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    _cache["fetched_at"] = None  # امسح الكاش عشان يجيب موقع جديد
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

# ── Main ──────────────────────────────────────────────────────────────────────
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
