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
CHAT_ID = "-1003763689916"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Accept": "text/html,application/xhtml+xml",
}


def get_nazar():
    """
    يسحب من madamnazar.io/madam-nazar-location-YYYY-MM-DD
    نفس المصدر الذي يستخدمه jeanropke
    يجرب اليوم، وإذا فشل يجرب أمس
    """
    for delta in [0, -1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y-%m-%d")
        url = f"https://madamnazar.io/madam-nazar-location-{date}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            logger.info(f"[{date}] status={resp.status_code}")

            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── الصورة ──────────────────────────────────────────
            img_url = None
            for attr in [("property", "og:image"), ("name", "twitter:image")]:
                tag = soup.find("meta", {attr[0]: attr[1]})
                if tag:
                    img_url = tag.get("content")
                    break

            # ── الوصف ───────────────────────────────────────────
            desc = ""
            for attr in [("property", "og:description"), ("name", "description")]:
                tag = soup.find("meta", {attr[0]: attr[1]})
                if tag:
                    desc = tag.get("content", "")
                    break

            # إذا ما في meta، نجرب نص الصفحة
            if not desc:
                p = soup.find("p")
                desc = p.get_text(strip=True) if p else ""

            logger.info(f"[{date}] desc={desc[:100]}")

            # ── استخراج الاسم والمنطقة ──────────────────────────
            # مثال: "point 7 — bluewater marsh (lemoyne) on February 14, 2026"
            patterns = [
                r"point\s*\d+\s*[—\-–]+\s*([^—\-–(]+?)\s*\(([^)]+)\)",
                r"point\s*\d+\s*[—\-–]+\s*([^—\-–(.]+)",
                r"located in\s+point\s*\d+\s*[—\-–]+\s*([^—\-–(]+?)\s*\(([^)]+)\)",
                r"Nazar.*?in\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\s*[\(\.]",
            ]

            for pattern in patterns:
                m = re.search(pattern, desc, re.IGNORECASE)
                if m:
                    location = m.group(1).strip().title()
                    region = m.group(2).strip().title() if len(m.groups()) >= 2 and m.group(2) else ""
                    if len(location) > 2:
                        logger.info(f"[{date}] ✅ {location}, {region}")
                        return img_url, location, region

        except Exception as e:
            logger.error(f"[{date}] error: {e}")

    logger.error("All attempts failed")
    return None, None, None


def get_countdown():
    now = datetime.now(timezone.utc)
    next_change = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= next_change:
        next_change += timedelta(days=1)
    total = int((next_change - now).total_seconds())
    return total // 3600, (total % 3600) // 60


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
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", send_nazar))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), text_nazar))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"كول[ي]?كتر"), text_collector))

    app.job_queue.run_daily(daily_auto_send, time=time(6, 1, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
