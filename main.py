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
# ENVIRONMENT VARIABLES
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM",
)
GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "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",
)


# =========================================================
# GROQ MODEL
# =========================================================

GROQ_MODEL = "qwen/qwen3.6-27b"


# =========================================================
# TRANSLATION PROMPT
# =========================================================

SYSTEM_PROMPT = """
Sen sadece otomatik çeviri yapan bir botsun.

GÖREV:
Gelen mesajın dilini otomatik algıla ve sadece diğer iki dile çevir.

DESTEKLENEN DİLLER:
Türkçe
Almanca
Rusça

KURALLAR:
1. Gelen mesaj Türkçeyse sadece Almanca ve Rusçaya çevir.
2. Gelen mesaj Almancaysa sadece Türkçe ve Rusçaya çevir.
3. Gelen mesaj Rusçaysa sadece Türkçe ve Almancaya çevir.
4. Gelen mesaj Azerbaycanca veya İngilizce ise Türkçe, Almanca ve Rusçaya çevir.
5. Kaynak dil hiçbir zaman tekrar çevrilmeyecek.
6. Mesaj çok kısa olsa bile mutlaka çevir. Örneğin:
   "Selam"
   "Naber"
   "Hım"
   "Evet"
   "Tamam"
   "İyi"
   "Ne?"
7. Çeviri birebir anlamı korumalıdır.
8. C1-C2 seviyesinde, ana dili konuşan bir insanın doğal kullanacağı şekilde çevir.
9. Argo, samimi konuşma, küfür, deyim veya günlük ifadeleri yapaylaştırmadan hedef dildeki doğal karşılığıyla çevir.
10. Mesajda olmayan hiçbir kelime, açıklama, yorum veya anlam EKLEME.
11. Mesajın anlamını değiştirme.
12. İsimleri, kullanıcı adlarını, özel isimleri ve sayıları gereksiz yere değiştirme.
13. Kesinlikle açıklama yapma.
14. Kesinlikle düşünme sürecini gösterme.
15. Kesinlikle "<think>", "analysis", "reasoning", "draft", "final answer" gibi ifadeler yazma.
16. Kesinlikle "çeviri:", "işte çeviri:", "anlamı:" gibi açıklamalar yazma.
17. SADECE aşağıdaki formatta çıktı ver.

ÇIKTI FORMATI:

🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]

veya kaynak Almancaysa:

🇹🇷 Türkçe: [çeviri]
🇷🇺 Rusça: [çeviri]

veya kaynak Rusçaysa:

🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]

veya kaynak Azerbaycanca/İngilizceyse:

🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]

SADECE BU SATIRLARI ÜRET. BAŞKA HİÇBİR ŞEY YAZMA.
"""


# =========================================================
# CLEAN BAD MODEL OUTPUT (KESİN SÜZGEÇ)
# =========================================================


def clean_response(text: str) -> str:
    if not text:
        return ""

    # 1. <think>...</think> bloklarını tamamen temizle
    text = re.sub(
        r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE
    )

    # 2. Satır satır inceleyip SADECE gerçek bayraklı çevirileri süz
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    valid_lines = []

    for line in lines:
        # Satır bayrakla (🇩🇪, 🇷🇺, 🇹🇷) başlıyorsa
        if re.match(r"^(🇩🇪|🇷🇺|🇹🇷)", line):
            # Taslak veya placeholder ifadeleri atla
            if (
                "[" in line
                or "]" in line
                or "Draft:" in line
                or "Translation" in line
            ):
                continue
            valid_lines.append(line)

    # Düşünme adımlarından sonra gelen EN SON gerçek çeviri satırlarını al
    if valid_lines:
        return "\n".join(
            valid_lines[-3:] if len(valid_lines) > 3 else valid_lines
        )

    return text.strip()


# =========================================================
# TRANSLATE WITH GROQ
# =========================================================


def translate_with_groq(text: str) -> str:
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY bulunamadı."

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    try:
        response = client.chat.completions.create(
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
        )

        message = response.choices[0].message
        result = message.content

        if not result:
            return "⚠️ Çeviri alınamadı."

        result = clean_response(result)

        if not result:
            return "⚠️ Çeviri alınamadı."

        logger.info("Translation completed successfully.")

        return result

    except Exception as error:
        logger.exception("Groq translation error")

        return "⚠️ Çeviri hatası:\n" + str(error)


# =========================================================
# TELEGRAM MESSAGE HANDLER
# =========================================================


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None or message.text is None:
        return

    text = message.text.strip()

    if not text or text.startswith("/"):
        return

    logger.info("Incoming message: %s", text)

    translation = translate_with_groq(text)

    await message.reply_text(
        translation,
        disable_web_page_preview=True,
    )


# =========================================================
# ERROR HANDLER
# =========================================================


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error("Telegram error: %s", context.error)


# =========================================================
# MAIN
# =========================================================


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı!")

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY bulunamadı!")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("🤖 VIYANA AI TRANSLATION BOT IS LIVE!")

    app.run_polling(drop_pending_updates=True)


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":
    main()
