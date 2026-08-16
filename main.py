import os
import json
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
# AYARLAR
# ============================================================

GROQ_API_KEY = "Gsk_6KsTInTXptZ2nXsEOVOvWGdyb3FYJ2PcphZFqQ9n9fWRdM2QMOZj"
TELEGRAM_BOT_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY bulunamadı.")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı.")

# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# ============================================================
# GROQ
# ============================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MODEL_NAME = "llama-3.1-8b-instant"

# ============================================================
# BİREBİR SADIK VE C2 ÇEVİRİ TALİMATI
# ============================================================

SYSTEM_PROMPT = """Sen metne tamamen sadık kalan, asla kelime veya anlam uydurmayan, C2 seviyesinde anadili gibi konuşan profesyonel bir çeviri motorusun.

KESİN KURALLAR:
1. Asla metne kendi kafandan veda (örn: "Пока", "Bis bald"), selam veya ek sohbet cümleleri EKLEME.
2. Kullanıcı ne yazdıysa (özel isimler, etiketler, argo, kısa ifadeler veya günlük sözler) dışına çıkmadan, tam olarak ne yazıldıysa onu hedef dildeki en doğal, akıcı ve C2 seviyesindeki insan tonuyla çevir. Ne eksik ne fazla!
3. Çıktın KESİNLİKLE sadece aşağıdaki JSON formatında olmalıdır. Başka hiçbir açıklama yazma:

{
  "detected_lang": "tr",
  "tr": "Türkçe çeviri",
  "de": "Almanca çeviri",
  "ru": "Rusça çeviri"
}
"""

# ============================================================
# ÇEVİRİ FONKSİYONU VE FİLTRELEME MANTIĞI
# ============================================================

def translate_text(text: str) -> str:
    try:
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
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.0,
        )

        if not response.choices:
            return ""

        content = response.choices[0].message.content

        if not content:
            return ""

        data = json.loads(content)

        detected = data.get("detected_lang", "").lower()
        tr_text = data.get("tr", "")
        de_text = data.get("de", "")
        ru_text = data.get("ru", "")

        result_lines = []

        if detected in ["tr", "turkish", "türkçe", "az", "azerice"]:
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        elif detected in ["de", "german", "almanca"]:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        elif detected in ["ru", "russian", "rusça"]:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")

        else:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error("API veya JSON Ayrıştırma hatası: %s", e)
        return ""

# ============================================================
# TELEGRAM MESAJ İŞLEYİCİ
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    if not message.text:
        return

    text = message.text.strip()

    if not text:
        return

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
        logger.error("Mesaj gönderme hatası: %s", e)

# ============================================================
# BOTU BAŞLAT
# ============================================================

def main():
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

    print("")
    print("🤖 VIYANA AI (BİREBİR SADIK C2 MODU)")
    print("")
    print("🌍 OTOMATİK ÇEVİRİ: AKTİF")
    print("⚙️ Sıcaklık: 0.0 (Asla Uydurmaz)")
    print("🧠 MODEL:", MODEL_NAME)
    print("==========================================")
    print("🚀 BOT BAŞLATILIYOR...")
    print("")

    app.run_polling()

# ============================================================
# PROGRAM
# ============================================================

if __name__ == "__main__":
    main()
