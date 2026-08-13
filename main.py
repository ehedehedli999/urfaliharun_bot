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
# AYARLAR
# ============================================================

# Anahtarlar koda sabitlendi
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
# ÇEVİRİ TALİMATI
# ============================================================

SYSTEM_PROMPT = """
Sen Viyana AI otomatik çeviri botusun.

GÖREVİN SADECE ÇEVİRİ YAPMAKTIR.

ÖNCE GELEN MESAJIN KAYNAK DİLİNİ TESPİT ET.

ÇOK ÖNEMLİ ÇEVİRİ KURALI:

1. AZERİCE GELİRSE:
   SADECE şu üç dile çevir:
   🇹🇷 Türkçe
   🇩🇪 Almanca
   🇷🇺 Rusça

2. İNGİLİZCE GELİRSE:
   SADECE şu üç dile çevir:
   🇹🇷 Türkçe
   🇩🇪 Almanca
   🇷🇺 Rusça

3. TÜRKÇE GELİRSE:
   SADECE:
   🇩🇪 Almanca
   🇷🇺 Rusça

4. ALMANCA GELİRSE:
   SADECE:
   🇹🇷 Türkçe
   🇷🇺 Rusça

5. RUSÇA GELİRSE:
   SADECE:
   🇹🇷 Türkçe
   🇩🇪 Almanca

KAYNAK DİLİ ASLA TEKRAR ÇEVİRME.

ÖRNEK:

Türkçe:
"Merhaba nasılsın?"

Cevap:
🇩🇪 Hallo, wie geht es dir?
🇷🇺 Привет, как дела?

ASLA:
🇹🇷 Merhaba nasılsın?
yazma.

---

Rusça:
"Как дела?"

Cevap:
🇹🇷 Nasılsın?
🇩🇪 Wie geht es dir?

ASLA:
🇷🇺 Как дела?
yazma.

---

Almanca:
"Wie geht es dir?"

Cevap:
🇹🇷 Nasılsın?
🇷🇺 Как дела?

ASLA:
🇩🇪 Wie geht es dir?
yazma.

---

Azerice:
"Necəsən?"

Cevap:
🇹🇷 Nasılsın?
🇩🇪 Wie geht es dir?
🇷🇺 Как дела?

---

İngilizce:
"How are you?"

Cevap:
🇹🇷 Nasılsın?
🇩🇪 Wie geht es dir?
🇷🇺 Как дела?

ÇEVİRİ KALİTESİ:

- Anlamı kesinlikle değiştirme.
- Kelime kelime mekanik çeviri yapma.
- Doğal ve akıcı çeviri yap.
- Deyimleri hedef dildeki doğal karşılığıyla aktar.
- Argo ve günlük konuşma dilini koru.
- Küfür varsa tonunu ve anlamını koru.
- İsimleri değiştirme.
- Sayıları değiştirme.
- Tarihleri değiştirme.
- Özel isimleri değiştirme.
- Kişi zamirlerini doğru koru.
- Cinsiyet bilgisini mümkün olduğunca doğru koru.
- Mesajın duygusunu ve tonunu koru.
- Ekstra açıklama yapma.
- Kullanıcıya cevap verme.
- Sohbet etme.
- Sadece çevirileri üret.

ÇOK ÖNEMLİ:

Eğer mesaj Türkçeyse Türkçe satırı YAZMA.

Eğer mesaj Almancaysa Almanca satırı YAZMA.

Eğer mesaj Rusçaysa Rusça satırı YAZMA.

Eğer mesaj Azericeyse üç dili de yaz.

Eğer mesaj İngilizceyse üç dili de yaz.

SADECE gerekli bayrakları ve çevirileri yaz.

Format:

🇹🇷 Türkçe çeviri
🇩🇪 Almanca çeviri
🇷🇺 Rusça çeviri

Gerekmeyen satırları kesinlikle yazma.
"""


# ============================================================
# ÇEVİRİ FONKSİYONU
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
        temperature=0.0,
    )

    if not response.choices:
        return ""

    content = response.choices[0].message.content

    if not content:
        return ""

    return content.strip()


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

            await message.reply_text(
                translated
            )

    except Exception as e:

        logger.error(
            "Çeviri hatası: %s",
            e,
        )


# ============================================================
# BOTU BAŞLAT
# ============================================================

def main():

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # SADECE OTOMATİK ÇEVİRİ
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("")
    print("==========================================")
    print("🤖 VIYANA AI")
    print("==========================================")
    print("🌍 OTOMATİK ÇEVİRİ: AKTİF")
    print("🇦🇿 Azerice → 3 dil")
    print("🇬🇧 İngilizce → 3 dil")
    print("🇹🇷 Türkçe → Almanca + Rusça")
    print("🇩🇪 Almanca → Türkçe + Rusça")
    print("🇷🇺 Rusça → Türkçe + Almanca")
    print("🧠 MODEL:", MODEL_NAME)
    print("🪙 MAX TOKEN: 500")
    print("==========================================")
    print("🚀 BOT BAŞLATILIYOR...")
    print("")

    app.run_polling()


# ============================================================
# PROGRAM
# ============================================================

if __name__ == "__main__":
    main()
