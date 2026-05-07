import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# إعدادات اللوق
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# التوكن حقك
TELEGRAM_TOKEN = "8202101663:AAH6ZqbN58J9YnpswBX8v_bqqSLL7gKlxWE"

def get_nazar():
    try:
        # الرابط المباشر للبيانات
        api_url = "https://madamnazar.io/data.json"
        
        # هيدرز قوية عشان الموقع ما يحظرنا
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://madamnazar.io/",
            "Origin": "https://madamnazar.io"
        }
        
        # محاولة طلب البيانات
        session = requests.Session()
        resp = session.get(api_url, headers=headers, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json()
            location_name = data.get("name", "Unknown Area")
            img = data.get("image", "assets/img/map.png")
            
            # تصحيح رابط الصورة
            if img.startswith('assets') or img.startswith('/assets'):
                img_url = f"https://madamnazar.io/{img.lstrip('/')}"
            else:
                img_url = img
                
            return img_url, location_name
        else:
            logger.error(f"خطأ من الموقع: {resp.status_code}")
            return None, None
            
    except Exception as e:
        logger.error(f"حدث خطأ: {e}")
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 هلا بك! أنا بوت مدام نزار. أرسل /nazar لموقع اليوم.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 الأوامر:\n/nazar - موقع مدام نزار\n/start - ترحيب")

async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رسالة مؤقتة
    status_msg = await update.message.reply_text("🔍 جاري جلب الموقع من الخريطة...")
    
    img_url, location = get_nazar()
    
    if img_url and location:
        caption = f"🔮 *موقع مدام نزار اليوم*\n\n📍 *المنطقة:* {location}\n\n_يتحدث الموقع يومياً 6:00 AM UTC_"
        await status_msg.delete()
        await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
    else:
        await status_msg.edit_text("❌ الموقع حالياً يرفض الاتصال، جربي مرة ثانية بعد دقيقة.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("nazar", nazar_command))
    
    logger.info("🤖 البوت شغال الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
