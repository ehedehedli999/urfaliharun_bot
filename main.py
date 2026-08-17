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
# MÜHİT DƏYİŞƏNLƏRİ (ENVIRONMENT VARIABLES)
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM")

GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1", "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"),
    os.getenv("GROQ_API_KEY_2", "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"),
    os.getenv("GROQ_API_KEY_3", "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"),
    os.getenv("GROQ_API_KEY_4", "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"),
    os.getenv("GROQ_API_KEY_5", "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"),
]
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
    """Rəsmi OpenAI SDK vasitəsilə Groq API-yə qoşulur və 5 açar arasında avtomatik keçid edir (Fallback)"""
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
            logger.warning(f"⚠️ Açar #{index} xəta verdi: {e}. Növbətiyə keçilir...")
    
    return "⚠️ Xəta: Heç bir Groq açarı cavab vermədi."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not text or text.startswith("/"):
        return

    translated = translate_with_groq(text)
    await message.reply_text(translated)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 BOT İŞƏ DÜŞDÜ VƏ QÜSURSUZ İŞLƏYİR!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
