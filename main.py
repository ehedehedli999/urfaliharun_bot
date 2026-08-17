import os
import json
import logging
import urllib.request

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from openai import OpenAI

# ============================================================
# 5'Lİ ZİNCİRVARİ EHTİYAT (FALLBACK) GROQ API AÇARLARI
# ============================================================

GROQ_API_KEYS = [
    "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",  # 1. Açar
    "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",  # 2. Açar
    "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",  # 3. Açar
    "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",  # 4. Açar
    "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",  # 5. Açar
]

TELEGRAM_BOT_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"
GROUP_CHAT_ID = ""  # ÖRNEK: "-1001234567890"

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

MODEL_NAME = "llama-3.1-8b-instant"

# ============================================================
# C2 ÇEVİRİ TALİMATI
# ============================================================

SYSTEM_PROMPT = """Sen metne tamamen sadık kalan, asla kelime veya anlam uydurmayan, C2 seviyesinde anadili gibi konuşan profesyonel bir çeviri motorusun.

KESİN KURALLAR:
1. Asla metne kendi kafandan veda (örn: "Пока", "Bis bald"), selam veya ek sohbet cümleleri EKLEME.
2. Kullanıcı ne yazdıysa dışına çıkmadan, tam olarak ne yazıldıysa onu hedef dildeki en doğal, akıcı ve C2 seviyesindeki insan tonuyla çevir. Ne eksik ne fazla!
3. Çıktın KESİNLİKLE sadece aşağıdaki JSON formatında olmalıdır. Başka hiçbir açıklama yazma:

{
  "detected_lang": "az",
  "tr": "Türkçe çeviri",
  "de": "Almanca çeviri",
  "ru": "Rusça çeviri",
  "en": "İngilizce çeviri"
}
"""

# ============================================================
# 5'Lİ DÖNGÜLÜ FALLBACK ÇEVİRİ FONKSİYONU
# ============================================================

def translate_text(text: str) -> str:
    content = ""
    
    for index, api_key in enumerate(GROQ_API_KEYS, start=1):
        if not api_key:
            continue
            
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                max_tokens=400,
                temperature=0.0,
            )
            
            if response.choices and response.choices[0].message.content:
                content = response.choices[0].message.content
                if index > 1:
                    logger.info(f"✅ Açar #{index} uğurla işə düşdü və çevirdi.")
                break
                
        except Exception as e:
            logger.warning(f"⚠️ Açar #{index} xəta verdi / limitə düşdü: {e}. Növbəti açara keçilir...")

    if not content:
        logger.error("❌ Bütün 5 açar da cavab vermədi və ya limitə düşdü!")
        return ""

    try:
        data = json.loads(content)

        detected = data.get("detected_lang", "").lower()
        tr_text = data.get("tr", "")
        de_text = data.get("de", "")
        ru_text = data.get("ru", "")
        en_text = data.get("en", "")

        result_lines = []

        if detected in ["tr", "turkish", "türkçe", "az", "azerice"]:
            if en_text: result_lines.append(f"🇬🇧 {en_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")
        elif detected in ["en", "english", "ingilis"]:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")
        elif detected in ["de", "german", "almanca"]:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if en_text: result_lines.append(f"🇬🇧 {en_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")
        elif detected in ["ru", "russian", "rusça"]:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if en_text: result_lines.append(f"🇬🇧 {en_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
        else:
            if tr_text: result_lines.append(f"🇹🇷 {tr_text}")
            if en_text: result_lines.append(f"🇬🇧 {en_text}")
            if de_text: result_lines.append(f"🇩🇪 {de_text}")
            if ru_text: result_lines.append(f"🇷🇺 {ru_text}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error("JSON Ayrıştırma hatası: %s", e)
        return ""

# ============================================================
# TELEGRAM MESAJ İŞLEYİCİ
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not text or text.startswith("/"):
        return

    if len(text) > 2000:
        await message.reply_text("⚠️ Mesaj çok uzun olduğu için çevrilmedi.")
        return

    try:
        translated = translate_text(text)
        if translated:
            await message.reply_text(translated)
    except Exception as e:
        logger.error(f"Mesaj gönderme hatası: {e}")

# ============================================================
# BOT AÇILIŞ TETİKLEYİCİSİ
# ============================================================

async def post_init(application):
    if GROUP_CHAT_ID:
        try:
            await application.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="🤖 Bot aktiv! 5-li avtomatik ehtiyat (Fallback) sistemi ilə işə hazırdır."
            )
            logger.info("Bot açılış mesajı gruba gönderildi.")
        except Exception as e:
            logger.error(f"Açılış mesajı hatası: {e}")

# ============================================================
# BOTU BAŞLAT
# ============================================================

def main():
    try:
        clear_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True"
        urllib.request.urlopen(clear_url, timeout=5)
        print("🧹 Eski Webhook temizlendi.")
    except Exception as ex:
        print(f"Webhook uyarı: {ex}")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 VIYANA AI (5-Lİ KOTA DÖNGÜLÜ ÇEVİRİ SİSTEMİ) BAŞLATILIYOR...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
