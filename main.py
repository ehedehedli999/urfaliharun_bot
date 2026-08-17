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

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Açarları yoxlayırıq və boşluqları təmizləyirik
GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
    os.getenv("GROQ_API_KEY_5"),
]
GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS if k and k.strip()]

logger.info(f"Yüklənən Groq açarlarının sayı: {len(GROQ_API_KEYS)}")

MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """Sen profesyonel bir çeviri motorusun. Kullanıcının yazdığı metni İngilizce, Almanca, Rusça ve Türkçe dillerinə çevir. 
Cevabını tam olaraq bu formatda ver, başqa heç bir izahat yazma:
🇬🇧 İngilizce: [...]
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]
"""

def translate_with_groq(text: str) -> str:
    if not GROQ_API_KEYS:
        logger.error("XƏTA: Heç bir Groq açarı tapılmadı! Render Environment Variables bölməsini yoxlayın.")
        return "⚠️ Xəta: Render-də Groq açarları tapılmadı."

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
            
            content = completion.choices[0].message.content
            if content:
                return content.strip()
                
        except Exception as e:
            logger.error(f"❌ Açar #{index} xəta verdi: {str(e)}")
    
    return "⚠️ Xəta: Bütün açarlar xəta verdi."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    translated = translate_with_groq(message.text.strip())
    await message.reply_text(translated)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Telegram xətası: {context.error}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("XƏTA: TELEGRAM_BOT_TOKEN tapılmadı!")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 BOT İŞƏ DÜŞDÜ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
