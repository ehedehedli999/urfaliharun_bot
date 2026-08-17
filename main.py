import logging
import os
import re

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# ENVIRONMENT
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM",
)
GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    "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",
)


# =========================================================
# GROQ MODEL
# =========================================================

GROQ_MODEL = "qwen/qwen3.6-27b"


# =========================================================
# TRANSLATION SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
Sen Viyana AI adlı profesyonel otomatik çeviri botusun.

GÖREVİN SADECE ÇEVİRİ YAPMAKTIR.

Gelen mesajın dilini otomatik olarak tespit et.

DİL KURALLARI:

1. Türkçe mesaj:
Sadece Almanca ve Rusçaya çevir.

🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]


2. Almanca mesaj:
Sadece Türkçe ve Rusçaya çevir.

🇹🇷 Türkçe: [çeviri]
🇷🇺 Rusça: [çeviri]


3. Rusça mesaj:
Sadece Türkçe ve Almancaya çevir.

🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]


4. İngilizce, Azerbaycanca veya başka bir dil:
Sadece Türkçe, Almanca ve Rusçaya çevir.

🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]


ÇEVİRİ KALİTESİ:

• C2 seviyesinde çeviri yap.
• Ana dili konuşan bir insanın yazacağı kadar doğal ve akıcı ol.
• Anlamı mümkün olduğunca birebir koru.
• Kullanıcının söylemediği hiçbir şeyi ekleme.
• Uydurma kelime, bilgi veya ifade oluşturma.
• Açıklama yapma.
• Yorum yapma.
• Özetleme yapma.
• Mesajı genişletme.
• Mesajı kısaltma.
• Duyguyu ve tonu koru.
• Argo ifadeleri doğal şekilde çevir.
• Küfür varsa anlamını koru.
• Deyimleri hedef dildeki doğal karşılığıyla çevir.
• Özel isimleri gereksiz yere değiştirme.
• Sayıları, tarihleri ve önemli bilgileri değiştirme.


ÇOK KISA MESAJLARI DA MUTLAKA ÇEVİR:

"Evet"
"Hayır"
"Tamam"
"Hmm"
"Naber"
"Selam"
"Merhaba"
"İyi"
"Yok"
"Var"
"Olur"

Tek kelimelik mesajları veya çok kısa mesajları ASLA görmezden gelme.


KESİNLİKLE ŞUNLARI YAZMA:

<think>
</think>
reasoning
analysis
düşünme süreci
"İşte çeviri"
"Tabii"
"Elbette"
"Here is the translation"

Kullanıcıya hiçbir açıklama verme.

SADECE nihai çevirileri gönder.
"""


# =========================================================
# THINK / REASONING TEMİZLEME
# =========================================================


def clean_response(text: str) -> str:
    if not text:
        return ""

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    text = re.sub(
        r"</?think>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</?analysis>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</?reasoning>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


# =========================================================
# GROQ TRANSLATION
# =========================================================


def translate_with_groq(text: str) -> str:
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY tapılmadı!"

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
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
            temperature=0.2,
            max_completion_tokens=1000,
            reasoning_effort="none",
            reasoning_format="hidden",
        )

        content = completion.choices[0].message.content

        if not content:
            return "⚠️ Çeviri alınamadı."

        content = clean_response(content)

        if not content:
            return "⚠️ Çeviri alınamadı."

        logger.info(
            "Çeviri uğurla tamamlandı: %s",
            GROQ_MODEL,
        )

        return content

    except Exception as e:
        logger.exception("Groq xətası")
        return "⚠️ Tərcümə xətası: " + str(e)


# =========================================================
# TELEGRAM MESSAGE HANDLER
# =========================================================


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not message.text:
        return

    text = message.text.strip()

    if text.startswith("/") or not text:
        return

    translated = translate_with_groq(text)

    await message.reply_text(
        translated,
        disable_web_page_preview=True,
    )


# =========================================================
# ERROR HANDLER
# =========================================================


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Telegram xətası: %s",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tapılmadı!")

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY tapılmadı!")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("🤖 VIYANA AI TƏRCÜMƏ BOTU HAZIRDIR!")

    app.run_polling(drop_pending_updates=True)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
