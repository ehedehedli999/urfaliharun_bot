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
You are Viyana AI, a professional translation bot.

YOUR ONLY TASK IS TRANSLATION.

Detect the language of the user's message automatically.

TRANSLATION RULES:

If the message is Turkish:
Translate it into German and Russian.

If the message is German:
Translate it into Turkish and Russian.

If the message is Russian:
Translate it into Turkish and German.

If the message is English, Azerbaijani, or another language:
Translate it into Turkish, German, and Russian.

IMPORTANT:

Translate even very short messages and single words.

Examples:
Selam
Naber
Nasılsın
Tamam
Evet
Hayır
Hmm
Olur
Yok
Var

NEVER ignore a short message.

TRANSLATION QUALITY:

- Translate at C1/C2 professional level.
- Make the translation sound completely natural to a native speaker.
- Preserve the exact meaning.
- Preserve the original tone and emotion.
- Preserve slang and informal language naturally.
- Do not invent words.
- Do not invent information.
- Do not add explanations.
- Do not add comments.
- Do not summarize.
- Do not expand the message.
- Do not shorten the message.
- Do not change names.
- Do not change numbers or dates.
- Do not add information that is not present in the original message.

OUTPUT FORMAT:

Turkish source:
🇩🇪 Almanca: TRANSLATION
🇷🇺 Rusça: TRANSLATION

German source:
🇹🇷 Türkçe: TRANSLATION
🇷🇺 Rusça: TRANSLATION

Russian source:
🇹🇷 Türkçe: TRANSLATION
🇩🇪 Almanca: TRANSLATION

Other language:
🇹🇷 Türkçe: TRANSLATION
🇩🇪 Almanca: TRANSLATION
🇷🇺 Rusça: TRANSLATION

VERY IMPORTANT:

Output ONLY the translations.

Do NOT output:
- reasoning
- analysis
- explanation
- planning
- steps
- "Translate"
- "Check Constraints"
- "Construct Output"
- "Here is the translation"
- "Done"
- [çeviri]
- <think>
- </think>
- <analysis>
- </analysis>
- <reasoning>
- </reasoning>

Never describe what you are doing.

Never repeat the user's original message.

Return only the final translations.
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
    lines = text.split("\n")
    valid_lines = []

    for line in lines:
        stripped = line.strip()
        # Satır bayrakla (🇩🇪, 🇷🇺, 🇹🇷) başlıyorsa
        if re.match(r"^(🇩🇪|🇷🇺|🇹🇷)", stripped):
            # Taslak/Placeholder olan satırları atla ([German Translation], [çeviri] vs.)
            if "[" in stripped or "]" in stripped:
                continue
            valid_lines.append(stripped)

    # Geçerli çeviri satırları bulunduysa sadece onları birleştir
    if valid_lines:
        return "\n".join(valid_lines)

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
