import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import time
import pytz

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "")  # اختياري - للإشعارات اليومية التلقائية

# أسماء المناطق (slug من اسم الصورة → اسم عربي/إنجليزي)
LOCATION_NAMES = {
    "afshuz":    "Flat Iron Lake / Tall Trees",
    "annesburg": "Annesburg / Roanoke Ridge",
    "benedict":  "Benedict Point / Flat Iron Lake",
    "butcher":   "Butcher Creek / Roanoke Ridge",
    "emerald":   "Emerald Ranch / Heartlands",
    "hanging":   "Hanging Dog Ranch / Big Valley",
    "lagras":    "Lagras / Bayou Nwa",
    "manzanita": "Manzanita Post / Big Valley",
    "meadows":   "Scarlett Meadows",
    "moonstone": "Moonstone Pond / Heartlands",
    "rhodes":    "Rhodes / Scarlett Meadows",
    "ringneck":  "Ringneck Creek / Heartlands",
    "thieves":   "Thieves' Landing / Flat Iron Lake",
    "tumbleweed":"Tumbleweed / Gaptooth Ridge",
    "valentine": "Valentine / Heartlands",
    "wallace":   "Wallace Station / Tall Trees",
    "macfarlane":"MacFarlane's Ranch / Flatneck Station",
    "lagras":    "Lagras / Bayou Nwa",
    "elysian":   "Elysian Pool / Roanoke Ridge",
    "flatneck":  "Flatneck Station / Heartlands",
    "downes":    "Downes Ranch / Heartlands",
    "cornwall":  "Cornwall Kerosene & Tar / Heartlands",
    "limpany":   "Limpany / Heartlands",
    "stillwater":"Stillwater Creek / Heartlands",
    "horseshoe": "Horseshoe Overlook / Heartlands",
    "catfish":   "Catfish Jacksons / Flat Iron Lake",
    "chadwick":  "Chadwick Farm / Bayou Nwa",
    "dewberry":  "Dewberry Creek / Lemoyne",
    "shady":     "Shady Belle / Bayou Nwa",
    "braithwaite":"Braithwaite Manor / Scarlett Meadows",
    "caliga":    "Caliga Hall / Lemoyne",
    "bolger":    "Bolger Glade / Bayou Nwa",
}


def get_nazar():
    """يسحب موقع مدام نزار من madamnazar.io"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        resp = requests.get("https://madamnazar.io", headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # نسحب الصورة من og:image (مبنية مسبقاً في HTML بدون JS)
        og_image = soup.find("meta", property="og:image")
        if not og_image:
            logger.warning("og:image tag not found")
            return None, None, None

        img_url = og_image.get("content", "")
        logger.info(f"Image URL: {img_url}")

        # نستخرج slug من اسم الملف: rdo_map_nazar_11_afshuz.jpg
        match = re.search(r'rdo_map_nazar_(\d+)_([a-z_]+)\.', img_url)
        if match:
            area_num = match.group(1)
            slug = match.group(2)
            # نحول slug لاسم قابل للقراءة
            location = LOCATION_NAMES.get(
                slug,
                slug.replace("_", " ").title()
            )
            return img_url, location, area_num

        # fallback: نرجع الـ URL بدون اسم
        return img_url, "Unknown Area", "?"

    except requests.RequestException as e:
        logger.error(f"Network error: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None, None, None


# ─── أوامر البوت ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *مرحباً! أنا بوت مدام نزار* 🔮\n\n"
        "أجيب لك موقع مدام نزار في *Red Dead Online* يومياً من موقع madamnazar.io\n\n"
        "📌 الأوامر:\n"
        "  /nazar — موقع مدام نزار اليوم\n"
        "  /help  — مساعدة",
        parse_mode="Markdown"
    )


async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")

    img_url, location, area_num = get_nazar()

    if img_url and location:
        caption = (
            f"🔮 *موقع مدام نزار اليوم*\n\n"
            f"📍 *المنطقة:*  {location}\n\n"
            f"_يتحدث الموقع يومياً الساعة 6:00 صباحاً UTC_"
        )
        await msg.delete()
        await update.message.reply_photo(
            photo=img_url,
            caption=caption,
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(
            "❌ ما قدرت أجيب الموقع.\n"
            "الموقع ممكن يكون تحت الصيانة، حاول مرة ثانية بعد شوي."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔮 *بوت مدام نزار — مساعدة*\n\n"
        "البوت يسحب موقع مدام نزار مباشرة من `madamnazar.io`\n\n"
        "🕕 الموقع يتحدث كل يوم الساعة *6:00 UTC*\n"
        "   (= 9:00 صباحاً بتوقيت الرياض)\n\n"
        "📌 الأوامر:\n"
        "  /nazar — اعرض الموقع الحالي مع الصورة\n"
        "  /start — رسالة الترحيب\n"
        "  /help  — هذه القائمة",
        parse_mode="Markdown"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    """إشعار تلقائي يومي (لو حطيت CHAT_ID)"""
    if not CHAT_ID:
        return
    img_url, location, _ = get_nazar()
    if img_url and location:
        caption = (
            f"🔮 *موقع مدام نزار اليوم*\n\n"
            f"📍 *المنطقة:*  {location}"
        )
        await context.bot.send_photo(
            chat_id=CHAT_ID,
            photo=img_url,
            caption=caption,
            parse_mode="Markdown"
        )


# ─── تشغيل البوت ──────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", nazar_command))
    app.add_handler(CommandHandler("help", help_command))

    # إشعار يومي الساعة 6:05 UTC (بعد 5 دقائق من تحديث الموقع)
    if CHAT_ID:
        app.job_queue.run_daily(
            daily_auto_send,
            time=time(6, 5, 0, tzinfo=pytz.UTC),
            name="daily_nazar"
        )
        logger.info(f"Daily notification enabled → chat_id: {CHAT_ID}")

    logger.info("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
