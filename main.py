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

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM"

# OpenRouter API açarları
OPENROUTER_API_KEYS = [
    "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",
    "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",
    "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",
    "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",
]

# 100% aktiv və pulsuz olan Google Gemma modeli
MODEL_NAME = "google/gemma-2-9b-it:free"

SYSTEM_PROMPT = """Sen C2 (Master) seviyesinde profesyonel bir çeviri ve lokalizasyon uzmanısın. Kullanıcının yazdığı metni; deyimleri, mecazları, kültürel bağlamı, tonu ve en ince anlam nuanslarını tamamen koruyarak İngilizce, Almanca, Rusça ve Türkçe dillerine kusursuz bir şekilde çevir. Kelimesi kelimesine değil, hedef dilde anadili olan birinin kuracağı en doğal, akıcı ve profesyonel cümle yapısını kullan.
Cevabını tam olarak bu formatta ver, başka hiçbir açıklama veya metin ekleme:
🇬🇧 İngilizce: [...]
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]
"""

def translate_with_openrouter(text: str) -> str:
    last_error = ""
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
            last_error = str(e)
            logger.error(f"❌ Açar #{index} xəta verdi: {last_error}")
    
    return f"⚠️ OpenRouter Xətası: {last_error}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    translated = translate_with_openrouter(message.text.strip())
    await message.reply_text(translated)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Telegram xətası: {context.error}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 BOT HAZIRDIR VƏ İŞLƏYİR!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

