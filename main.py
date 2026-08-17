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

# OpenRouter açarlarını mühit dəyişənlərindən oxuyuruq
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
    os.getenv("OPENROUTER_API_KEY_4"),
]
OPENROUTER_API_KEYS = [k.strip() for k in OPENROUTER_API_KEYS if k and k.strip()]

logger.info(f"Yüklənən OpenRouter açarlarının sayı: {len(OPENROUTER_API_KEYS)}")

# Ən sərfəli və pulsuz model
MODEL_NAME = "meta-llama/llama-3-8b-instruct:free"

# C2 Səviyyəli Professional Tərcümə Promptu
SYSTEM_PROMPT = """Sen C2 (Master) seviyesinde profesyonel bir çeviri ve lokalizasyon uzmanısın. Kullanıcının yazdığı metni; deyimleri, mecazları, kültürel bağlamı, tonu ve en ince anlam nuanslarını (nuance) tamamen koruyarak İngilizce, Almanca, Rusça ve Türkçe dillerine kusursuz bir şekilde çevir. Kelimesi kelimesine değil, hedef dilde anadili olan birinin kuracağı en doğal, akıcı ve profesyonel cümle yapısını kullan.
Cevabını tam olarak bu formatta ver, başka hiçbir açıklama veya metin ekleme:
🇬🇧 İngilizce: [...]
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]
"""

def translate_with_openrouter(text: str) -> str:
    if not OPENROUTER_API_KEYS:
        logger.error("XƏTA: Heç bir OpenRouter açarı tapılmadı!")
        return "⚠️ Xəta: Render-də OpenRouter açarları tapılmadı."

    for index, api_key in enumerate(OPENROUTER_API_KEYS, start=1):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=600,
                temperature=0.1
            )
            
            content = completion.choices[0].message.content
            if content:
                return content.strip()
                
        except Exception as e:
            logger.error(f"❌ Açar #{index} xəta verdi: {str(e)}")
    
    return "⚠️ Xəta: Bütün OpenRouter açarları limitə çatdı və ya xəta verdi."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    translated = translate_with_openrouter(message.text.strip())
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
    
    logger.info(f"🤖 C2 TƏRCÜMƏ BOTU İŞƏ DÜŞDÜ! Model: {MODEL_NAME}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

