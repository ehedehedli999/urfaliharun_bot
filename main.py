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
# API AYARLARI
# ============================================================

# Anahtarlar doğrudan koda eklendi
GROQ_API_KEY = "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"
TELEGRAM_BOT_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY bulunamadı.")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı.")


# ============================================================
# GROQ
# ============================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MODEL_NAME = "llama-3.1-8b-instant"


# ============================================================
# ÇEVİRİ TALİMATI
# ============================================================

SYSTEM_PROMPT = """
Sen Viyana AI otomatik çeviri botusun.

SADECE ÇEVİRİ YAP.

Türkçe veya Azerice → Almanca + Rusça
Rusça → Türkçe + Almanca
Almanca → Türkçe + Rusça
İngilizce → Türkçe + Almanca + Rusça

Kurallar:
- Anlamı değiştirme.
- Kelime kelime mekanik çeviri yapma.
- Deyimleri doğal hedef dil karşılığıyla çevir.
- Argo ve günlük konuşma tonunu koru.
- Küfür varsa anlamını ve tonunu koru.
- İsimleri, sayıları ve tarihleri değiştirme.
- Gereksiz açıklama yapma.
- Kaynak dil ile aynı dili tekrar çevirme.

Çıktı:

🇹🇷 Türkçe çeviri
🇩🇪 Almanca çeviri
🇷🇺 Rusça çeviri

Gerekmeyen dilleri yazma.
"""


# ============================================================
# ÇEVİRİ
# ============================================================

def translate_text(text: str) -> str:

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        max_tokens=500,
        temperature=0.1,
    )

    if not response.choices:
        return ""

    content = response.choices[0].message.content

    return content.strip() if content else ""


# ============================================================
# TELEGRAM MESAJLARI
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message

    if not message or not message.text:
        return

    text = message.text.strip()

    if not text:
        return

    # Gereksiz yüksek kullanımın önüne geç
    if len(text) > 2000:
        await message.reply_text(
            "⚠️ Mesaj çok uzun olduğu için çevrilmedi."
        )
        return

    try:

        translated = translate_text(text)

        if translated:
            await message.reply_text(translated)

    except Exception as e:

        logging.error("Çeviri hatası: %s", e)


# ============================================================
# BAŞLAT
# ============================================================

def main():

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("====================================")
    print("🤖 VIYANA AI AKTİF")
    print("🌍 Otomatik çeviri: AKTİF")
    print("🧠 Model:", MODEL_NAME)
    print("🪙 Max output: 500 token")
    print("💰 Ekonomik mod: AKTİF")
    print("====================================")

    app.run_polling()


if __name__ == "__main__":
    main()
