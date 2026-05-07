import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# إعدادات اللوكس لمراقبة الأخطاء
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- التوكن حقك (مكتوب صح بدون os.environ عشان ما يكرش) ---
TELEGRAM_TOKEN = "8202101663:AAH6ZqbN58J9YnpswBX8v_bqqSLL7gKlxWE"

def get_nazar():
    """سحب البيانات من الرابط المباشر لتجنب حماية الموقع"""
    try:
        # رابط البيانات المباشر (أسرع وأضمن)
        api_url = "https://madamnazar.io/data.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://madamnazar.io/"
        }
        
        resp = requests.get(api_url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            location_name = data.get("name", "Unknown Area")
            img = data.get("image", "")
            
            # تصحيح رابط الصورة
            if img.startswith('assets') or img.startswith('/assets'):
                img_url = f"https://madamnazar.io/{img.lstrip('/')}"
            else:
                img_url = img if img else "https://madamnazar.io/assets/img/map.png"
                
            return img_url, location_name
        else:
            logger.error(f"الموقع رد برمز خطأ: {resp.status_code}")
            return None, None
            
    except Exception as e:
        logger.error(f"حدث خطأ أثناء سحب البيانات: {e}")
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔮 أهلاً بك! أنا
