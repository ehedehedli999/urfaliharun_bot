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

GROQ_API_KEY = "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"
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
# ÇEVİRİ TALİMATI (GELİŞTİRİLMİŞ DOĞAL ÇEVİRİ PROMPTU)
# ============================================================

SYSTEM_PROMPT = """Sen Viyana AI profesyonel sohbet çevirmenisin. Görevin, gelen Telegram mesajının dilini doğru tespit etmek ve mesajı Türkçe, Almanca ve Rusçaya kusursuz bir şekilde çevirmektir.
Kullanıcılar Türkçe karakter kullanmadan (örn: "gunaydin", "nasilsiniz"), argo, deyim veya günlük sokak diliyle yazabilirler.

ÇOK ÖNEMLİ KURALLAR:
1. Asla kelimesi kelimesine (robotik) çeviri yapma! Deyimleri, argoları, şakaları ve günlük konuşmaları hedef dildeki en doğal, akıcı ve günlük karşılığıyla çevir.
2. Çıktın KESİNLİKLE sadece aşağıdaki JSON formatında olmalıdır. Başka hiçbir açıklama, sohbet veya not yazma:

{
  "detected_lang": "tr", 
  "tr": "Türkçe doğal çeviri metni",
  "de": "Almanca doğal çeviri metni",
  "ru": "Rusça doğal çeviri metni"
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
            # JSON formatında dönmeye zorluyoruz
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.3, # Doğal ve akıcı konuşma çevirisi için optimize edildi
        )

        if not response.choices:
            return ""

        content = response.choices[0].message.content

        if not content:
            return ""

        # JSON verisini Python sözlüğüne çevir
        data = json.loads(content)

        detected = data.get("detected_lang", "").lower()
        tr_text = data.get("tr", "")
        de_text = data.get("de", "")
        ru_text = data.get("ru", "")

        result_lines = []

        # ====================================================
        # HANGİ DİLLERİN GÖSTERİLECEĞİNE PYTHON KARAR VERİYOR
        # ====================================================
        if detected in ["tr", "turkish", "türkçe", "az", "azerice"]:
            # Türkçe/Azerice ise sadece Almanca ve Rusça
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        elif detected in ["de", "german", "almanca"]:
            # Almanca ise sadece Türkçe ve Rusça
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        elif detected in ["ru", "russian", "rusça"]:
            # Rusça ise sadece Türkçe ve Almanca
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")

        else:
            # Diğer diller için 3 dil gösterilir
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        # Listeyi alt alta metin haline getirip döndür
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

    # Çok uzun mesajları ekonomik kullanım için engelle
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
    print("==========================================")
    print("🤖 VIYANA AI (GELİŞMİŞ DOĞAL ÇEVİRİ MODU)")
    print("==========================================")
    print("🌍 OTOMATİK ÇEVİRİ: AKTİF")
    print("⚙️ Filtreleme: PYTHON SİSTEMİ")
    print("🇦🇿 Azerice/Türkçe → Almanca + Rusça")
    print("🇩🇪 Almanca → Türkçe + Rusça")
    print("🇷🇺 Rusça → Türkçe + Almanca")
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
