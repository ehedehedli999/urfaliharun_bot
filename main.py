import logging
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

# Token'lar doğrudan koda eklendi
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
XAI_API_KEY = "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"

# API Endpoint & Model Ayarları
XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "mixtral-8x7b-32768"

CHAT_MODES = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

SMART_PROMPT = """
Sen Urfalı Harun Bot'un Zeki modusun.
Çok zeki, bilgili, analitik, kültürlü ve mantıklı konuş.
Kullanıcının sorusunu dikkatlice analiz et.
Doğru, doğal ve anlaşılır cevap ver.
Kullanıcı hangi dilde yazıyorsa SADECE o dilde cevap ver.
Rusça → Rusça.
Türkçe → Türkçe.
Almanca → Almanca.
Başka dile geçme ve kullanıcı istemedikçe çeviri yapma.
Gereksiz giriş ve takip soruları kullanma.
Doğrudan cevap ver.
"""

AGGRESSIVE_PROMPT = """
Sen Urfalı Harun Bot'un Agresif modusun.
Sert, özgüvenli, direkt, keskin, hafif alaycı ve lafını esirgemeyen bir tarzda konuş.
Kullanıcının konuşma tarzına uyum sağla.
Gereksiz yere yumuşatma.
Kullanıcı hangi dilde yazıyorsa SADECE o dilde cevap ver.
Rusça → Rusça.
Türkçe → Türkçe.
Almanca → Almanca.
Başka dile geçme ve kullanıcı istemedikçe çeviri yapma.
Ciddi tehdit, şiddet teşviki veya nefret söylemi oluşturma.
Doğrudan cevap ver.
"""

TRANSLATION_PROMPT = """
Sen C1-C2 seviyesinde profesyonel bir çevirmensin.
SADECE Türkçe, Rusça ve Almanca arasında çeviri yap.

Kurallar:
Rusça → Türkçe + Almanca
Türkçe → Rusça + Almanca
Almanca → Türkçe + Rusça

Başka dilleri destekleme.
Çeviriler doğal, akıcı, bağlama uygun ve C1 seviyesinde olsun.
Kelime kelime mekanik çeviri yapma.
Anlamı, tonu, duyguyu, deyimleri ve konuşma tarzını koru.

Sadece ilgili iki çeviriyi göster.

Rusça:
Türkçe: ...
Almanca: ...

Türkçe:
Rusça: ...
Almanca: ...

Almanca:
Türkçe: ...
Rusça: ...

Kaynak metni tekrar yazma.
Başka açıklama yapma.

Desteklenmeyen bir dil gelirse sadece:
DESTEKLENMEYEN_DIL
yaz.
"""


async def query_grok(prompt: str, system_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(XAI_URL, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            try:
                content = result["choices"][0]["message"]["content"]
                if content:
                    return content.strip()
            except (KeyError, IndexError):
                raise Exception("API beklenmeyen bir yanıt döndürdü.")

        error_text = response.text
        try:
            error_json = response.json()
            if isinstance(error_json, dict) and "error" in error_json:
                error_text = error_json["error"].get("message", error_text)
        except Exception:
            pass

        if response.status_code == 401:
            raise Exception("API anahtarı geçersiz.")
        elif response.status_code == 403:
            raise Exception("API erişimi reddedildi.")
        elif response.status_code == 404:
            raise Exception("Model veya endpoint bulunamadı.")
        elif response.status_code == 429:
            raise Exception("API kullanım limitine ulaşıldı.")

        raise Exception(f"HTTP {response.status_code}: {error_text}")


async def send_long_message(message, text: str):
    if not text:
        return

    for start in range(0, len(text), 4000):
        await message.reply_text(text[start : start + 4000])


def bot_mentioned(message, bot_username: str) -> bool:
    if not bot_username:
        return False

    text = message.text or ""
    mention = f"@{bot_username}".lower()

    if mention in text.lower():
        return True

    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                try:
                    value = text[entity.offset : entity.offset + entity.length]
                    if value.lower() == mention:
                        return True
                except Exception:
                    pass

    return False


def remove_bot_mention(text: str, bot_username: str) -> str:
    if not bot_username:
        return text.strip()
    return text.replace(f"@{bot_username}", "").strip()


def detect_mode(text: str):
    value = text.lower().strip()
    if value in ["agresif", "agresif ol", "agresif moda geç", "agresif moda geç."]:
        return "aggressive"
    if value in ["zeki", "zeki ol", "zeki moda geç", "zeki moda geç."]:
        return "smart"
    return None


async def handle_ai(message, text: str, mode: str):
    prompt = AGGRESSIVE_PROMPT if mode == "aggressive" else SMART_PROMPT

    try:
        await message.chat.send_action(action="typing")
        answer = await query_grok(text, prompt)
        await send_long_message(message, answer)
    except Exception as e:
        logger.error("AI hatası: %s", e)
        await message.reply_text(f"⚠️ AI Hatası:\n{e}")


async def handle_translation(message, text: str):
    try:
        await message.chat.send_action(action="typing")
        result = await query_grok(text, TRANSLATION_PROMPT)

        if result.strip() == "DESTEKLENMEYEN_DIL":
            return

        await send_long_message(message, result)
    except Exception as e:
        logger.error("Çeviri hatası: %s", e)
        await message.reply_text(f"⚠️ Çeviri Hatası:\n{e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not text:
        return

    chat_id = message.chat_id
    bot_username = context.bot.username or ""

    mentioned = bot_mentioned(message, bot_username)

    if mentioned:
        clean_text = remove_bot_mention(text, bot_username)
        new_mode = detect_mode(clean_text)

        if new_mode:
            CHAT_MODES[chat_id] = new_mode
            msg = "😈 Agresif moda geçtim." if new_mode == "aggressive" else "🧠 Zeki moda geçtim."
            await message.reply_text(msg)
            return

        if not clean_text:
            return

        mode = CHAT_MODES.get(chat_id, "smart")
        await handle_ai(message, clean_text, mode)
        return

    await handle_translation(message, text)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Telegram hatası:", exc_info=context.error)


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)

    logger.info("Urfalı Harun Bot başlatılıyor...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
