import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from openai import OpenAI

# ============================================================
# LOGLAMA QURULUMU
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# MÜHİT DƏYİŞƏNLƏRİ (RENDER ÜÇÜN)
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# API açarlarını Render-in Environment Variables bölməsindən avtomatik oxuyur
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
    os.getenv("GROQ_API_KEY_5"),
]
# Boş olmayan açarları siyahıya alır
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]

MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """Sen profesyonel bir çeviri motorusun. Kullanıcının yazdığı metni İngilizce, Almanca, Rusça ve Türkçe dillerinə çevir. 
Cevabını tam olaraq bu formatda ver, başqa heç bir izahat yazma:
🇬🇧 İngilizce: [...]
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]
"""

def translate_with_groq(text: str) -> str:
    """Açarlar arasında keçid edərək Groq API-yə qoşulur"""
    for index, api_key in enumerate(GROQ_API_KEYS, start=1):
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=api_key
            )
            
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=400,
                temperature=0.0
            )
            
            return completion.choices[0].message.content.strip()
                
        except Exception as e:
            logger.warning(f"⚠️ Açar #{index} xəta verdi: {e}. Növbətiyə keçilir...")
    
    return "⚠️ Xəta: Heç bir Groq açarı cavab vermədi."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    translated = translate_with_groq(message.text.strip())
    await message.reply_text(translated)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Botun çöküşünü əngəlləyir"""
    logger.error(f"Xəta baş verdi: {context.error}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("XƏTA: TELEGRAM_BOT_TOKEN mühit dəyişəni təyin olunmayıb!")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("🤖 BOT UĞURLA İŞƏ DÜŞDÜ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
