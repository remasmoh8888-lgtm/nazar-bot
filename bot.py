import os
import re
import logging
import threading
import requests
from bs4 import BeautifulSoup
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import time
import pytz

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "")

# ─── Keep-Alive Server (عشان Replit ما ينام) ─────────────────

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    logger.info(f"Keep-alive server on port {port}")
    server.serve_forever()


# ─── Scraping ─────────────────────────────────────────────────
# المصدر: coyotejack.net — WordPress يتحدث يومياً الساعة 6 UTC
# كل محتواه موجود في HTML بدون حاجة لـ JavaScript

def get_nazar():
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(
            "https://www.coyotejack.net/where-is-madam-nazar/",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ابحث عن العنوان الذي يحتوي "Where is Madam Nazar Today?"
        for h2 in soup.find_all("h2"):
            if "Where is Madam Nazar Today?" in h2.get_text():
                # النص: "Where is Madam Nazar Today? – 07 May"
                date_match = re.search(r'–\s*(.+)', h2.get_text())
                date_str = date_match.group(1).strip() if date_match else ""

                # الفقرة التالية = وصف الموقع
                location_p = h2.find_next_sibling("p")
                location_text = location_p.get_text(strip=True) if location_p else ""

                # الصورة التالية = خريطة الموقع
                img_tag = h2.find_next("img")
                img_url = None
                if img_tag:
                    # نأخذ الصورة بأعلى جودة متاحة
                    img_url = (
                        img_tag.get("data-src")
                        or img_tag.get("src")
                        or img_tag.get("data-lazy-src")
                    )

                logger.info(f"Location: {location_text} | Date: {date_str} | Image: {img_url}")
                return img_url, location_text, date_str

        logger.warning("Section 'Where is Madam Nazar Today?' not found")
        return None, None, None

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return None, None, None


# ─── Bot Commands ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *مرحباً! أنا بوت مدام نزار* 🔮\n\n"
        "أجيب لك موقع مدام نزار في *Red Dead Online* يومياً\n\n"
        "📌 الأوامر:\n"
        "  /nazar — موقع مدام نزار اليوم\n"
        "  /help  — مساعدة",
        parse_mode="Markdown"
    )


async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار...")
    img_url, location, date_str = get_nazar()

    if location:
        caption = (
            f"🔮 *موقع مدام نزار — {date_str}*\n\n"
            f"📍 {location}\n\n"
            f"_يتحدث الموقع يومياً الساعة 6:00 UTC_"
        )
        await msg.delete()
        if img_url:
            try:
                await update.message.reply_photo(
                    photo=img_url,
                    caption=caption,
                    parse_mode="Markdown"
                )
                return
            except Exception as e:
                logger.error(f"Photo send failed: {e}")
        # fallback لو الصورة ما اشتغلت
        await update.message.reply_text(caption, parse_mode="Markdown")
    else:
        await msg.edit_text(
            "❌ ما قدرت أجيب الموقع.\n"
            "جرب مرة ثانية بعد شوي، أو تحقق من:\n"
            "madamnazar.io"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔮 *بوت مدام نزار*\n\n"
        "يسحب موقع مدام نزار من `coyotejack.net`\n\n"
        "🕕 يتحدث كل يوم *6:00 UTC* = 9:00 صباحاً بالرياض\n\n"
        "الأوامر:\n"
        "  /nazar — الموقع الحالي مع الصورة\n"
        "  /start — رسالة الترحيب",
        parse_mode="Markdown"
    )


async def daily_auto_send(context: ContextTypes.DEFAULT_TYPE):
    """إشعار تلقائي يومي — تفعّله بوضع CHAT_ID في المتغيرات"""
    if not CHAT_ID:
        return
    img_url, location, date_str = get_nazar()
    if location:
        caption = (
            f"🔮 *موقع مدام نزار — {date_str}*\n\n"
            f"📍 {location}"
        )
        if img_url:
            try:
                await context.bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=img_url,
                    caption=caption,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=caption,
            parse_mode="Markdown"
        )


# ─── Main ─────────────────────────────────────────────────────

def main():
    threading.Thread(target=run_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nazar", nazar_command))
    app.add_handler(CommandHandler("help", help_command))

    if CHAT_ID:
        # إشعار يومي الساعة 6:10 UTC (10 دقائق بعد تحديث الموقع)
        app.job_queue.run_daily(
            daily_auto_send,
            time=time(6, 10, 0, tzinfo=pytz.UTC)
        )
        logger.info(f"Daily notification → chat_id: {CHAT_ID}")

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
