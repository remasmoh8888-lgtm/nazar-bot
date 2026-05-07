import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# إعدادات اللوق عشان نشوف المشاكل
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# التوكن حقك مباشرة بدون أخطاء أقواس
TELEGRAM_TOKEN = "8202101663:AAH6ZqbN58J9YnpswBX8v_bqqSLL7gKlxWE"

def get_nazar():
    try:
        # استخدام هيدرز عشان الموقع ما يحظر البوت
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # جلب البيانات من الـ API حق الموقع
        resp = requests.get("https://madamnazar.io/data.json", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        location_name = data.get("name", "Unknown Area")
        img_url = data.get("image", "")
        
        # تصحيح رابط الصورة إذا كان ناقص
        if img_url and img_url.startswith('/'):
            img_url = f"https://madamnazar.io{img_url}"
        elif not img_url:
            img_url = "https://madamnazar.io/assets/img/map.png"
            
        return img_url, location_name
    except Exception as e:
        logger.error(f"Error in get_nazar: {e}")
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 هلا بك! أرسل /nazar عشان أعلمك مكان مدام نزار اليوم.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 الأوامر المتاحة:\n/nazar - موقع مدام نزار\n/start - ترحيب")

async def nazar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 جاري سحب الموقع من الخريطة...")
    img_url, location = get_nazar()
    
    if img_url and location:
        caption = f"🔮 *موقع مدام نزار اليوم*\n\n📍 *المنطقة:* {location}\n\n_يتحدث الموقع يومياً 6:00 AM UTC_"
        await msg.delete()
        await update.message.reply_photo(photo=img_url, caption=caption, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ فشل البوت في الاتصال بالموقع، جرب مرة ثانية بعد شوي.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("nazar", nazar_command))
    
    logger.info("🤖 البوت شغال الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
