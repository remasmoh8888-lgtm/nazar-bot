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

# تنبيه أمني: يفضل دائماً وضع التوكنز في ملف .env
TELEGRAM_TOKEN = "8372609971:AAE80LAq2iTKqTVqPRglepIzAv21DNXNPB0"
CHAT_ID = "8202101663"
COLLECTORS_MAP = "https://jeanropke.github.io/RDR2CollectorsMap/"


# ─── السحب من madamnazar.io ──────────────────────────────────

def get_nazar():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        # جلب الصفحة الرئيسية للموقع
        resp = requests.get("https://madamnazar.io/", headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # جلب اسم المنطقة المحددة (مثال: Plainview)
        heading_element = soup.find("h2", id="location-heading")
        # جلب المنطقة الكبرى (مثال: New Austin)
        region_element = soup.find("h3", id="region-heading")
        # جلب رابط الصورة الخاصة بالموقع
        img_element = soup.find("img", id="location-image")

        if heading_element and region_element:
            spot = heading_element.get_text(strip=True)
            region = region_element.get_text(strip=True)
            full_location = f"{spot} ({region})"
            
            img_url = ""
            if img_element and img_element.get("src"):
                src = img_element["src"]
                # تحويل الرابط النسبي إلى رابط كامل إذا لزم الأمر
                img_url = src if src.startswith("http") else f"https://madamnazar.io{src}"

            logger.info(f"Location Found: {full_location} | Image: {img_url}")
            return img_url, full_location

        return None, None

    except Exception as e:
        logger.error(f"Scraping error from madamnazar.io: {e}")
        return None, None


# ─── الأوامر ──────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "˚˖𓍢ִ໋❀ يا هلا والله في بوت نزار\n\n"
        "📍 /nazar أو اكتب 'نزار' لارسال موقع نزار.\n\n"
        "🌸 /map : لرابط خريطة الكولكتر التفاعلية.\n\n"
        "صيد موفق يا كولكترز! 🏇🎖️"
    )


async def send_nazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري البحث عن موقع مدام نزار من المصدر الجديد...")
    img_url, spot = get_nazar()

    if spot:
        caption = f"📍 *{spot}*"
        await msg.delete()
        if img_url:
            try:
                await update.message.reply_photo(
                    photo=img_url, caption=caption, parse_mode="Markdown"
                )
                return
            except Exception as e:
                logger.error(f"Photo failed to send: {e}")
        
        # في حال فشل إرسال الصورة، يتم إرسال النص فقط
        await update.message.reply_text(caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ ما قدرت أجيب الموقع حالياً، جرب مرة ثانية لاحقاً.")


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
                await context.bot.send_photo(
                    chat_id=CHAT_ID, photo=img_url,
                    caption=caption, parse_mode="Markdown"
                )
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
    
    # تحسين الفلتر ليتفاعل مع كلمة نزار بشكل مرن
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"نزار"), text_nazar))
    
    # جدولة الإرسال التلقائي اليومي
    app.job_queue.run_daily(daily_auto_send, time=time(6, 10, 0, tzinfo=pytz.UTC))

    logger.info("🤖 Bot started successfully with madamnazar.io source!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
