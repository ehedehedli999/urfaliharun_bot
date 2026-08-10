import logging
import os
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Koda doğrudan eklenen Token'ların
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
XAI_API_KEY = "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"

# Groq API Endpoint & Güncel Model (Llama 3.3 70B)
XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.3-70b-versatile"

CHAT_MODES = {}
TRANSLATION_SETTINGS = {}  # Genel çeviri durumu (True / False)
DISABLED_LANGUAGES = {}    # Grup bazlı kapatılan diller {chat_id: set("de", "ru", "tr", "en")}

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
İngilizce → İngilizce.
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
İngilizce → İngilizce.
Başka dile geçme ve kullanıcı istemedikçe çeviri yapma.
Ciddi tehdit, şiddet teşviki veya nefret söylemi oluşturma.
Doğrudan cevap ver.
"""

TRANSLATION_PROMPT = """
Sen hedef dillerin kültürüne, deyimlerine, argosuna ve günlük konuşma kalıplarına %100 hakim, anadili seviyesinde profesyonel bir uzmansın.
SADECE Türkçe, Rusça, Almanca ve İngilizce dilleri arasında çeviri yap.

GÖREVİN VE ÇEVİRİ FELSEFEN:
- Asla mekanik veya doğrudan (birebir) sözlük çevirisi yapma.
- Metnin duygu tonunu, samimiyetini, vurgusunu ve alt metnini tam olarak koru.
- Çevirilerin sanki Londra'da, Moskova'da, Berlin'de veya İstanbul'da doğup büyümüş bir sokak/günlük hayat yerlisi tarafından yazılmış gibi tam anadil doğallığında olmalı (Native-like fluency).
- Metindeki argo, jargon, sokak dili veya kalıpları hedef dildeki EN BİREBİR KARŞILIĞI olan deyim ve ifadelerle değiştir.

KURAL:
Gelen metnin dilini tespit et ve onu DİĞER ÜÇ DİLE çevir.
- Rusça ise → Türkçe, Almanca ve İngilizce'ye çevir.
- Türkçe ise → Rusça, Almanca ve İngilizce'ye çevir.
- Almanca ise → Türkçe, Rusça ve İngilizce'ye çevir.
- İngilizce ise → Türkçe, Rusça ve Almanca'ya çevir.

ÇIKTI FORMATI:
Sadece ilgili çevirileri göster. Giriş metni, açıklama veya "İşte çeviriniz" gibi ibareler ASLA ekleme.

Örnek Format:
Türkçe: ...
Almanca: ...
İngilizce: ...

Eğer metin bu dört dilden (Türkçe, Rusça, Almanca, İngilizce) biri değilse SADECE şu kelimeyi yaz:
DESTEKLENMEYEN_DIL
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
        "temperature": 0.5,
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


def filter_disabled_languages(chat_id: int, translation_text: str) -> str:
    """Kapatılmış dilleri çeviri sonucundan temizler."""
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    if not disabled:
        return translation_text

    lines = translation_text.split("\n")
    filtered_lines = []
    
    for line in lines:
        lower_line = line.lower()
        if "almanca:" in lower_line and "de" in disabled:
            continue
        if "rusça:" in lower_line and "ru" in disabled:
            continue
        if "türkçe:" in lower_line and "tr" in disabled:
            continue
        if "ingilizce:" in lower_line and "en" in disabled:
            continue
        filtered_lines.append(line)

    result = "\n".join(filtered_lines).strip()
    return result


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


async def handle_translation(message, text: str, chat_id: int):
    try:
        await message.chat.send_action(action="typing")
        result = await query_grok(text, TRANSLATION_PROMPT)

        if result.strip() == "DESTEKLENMEYEN_DIL":
            return

        # Kapatılan dilleri temizle
        final_result = filter_disabled_languages(chat_id, result)

        if final_result:
            await send_long_message(message, final_result)
    except Exception as e:
        logger.error("Çeviri hatası: %s", e)
        await message.reply_text(f"⚠️ Çeviri Hatası:\n{e}")


# Otomatik çeviriyi komple açma/kapatma komutu
async def toggle_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_status = TRANSLATION_SETTINGS.get(chat_id, True)
    new_status = not current_status
    TRANSLATION_SETTINGS[chat_id] = new_status

    if new_status:
        await update.effective_message.reply_text("🌐 Otomatik çeviri **AÇILDI**.")
    else:
        await update.effective_message.reply_text("🚫 Otomatik çeviri **KAPATILDI**.")


# Özel Dil Kapatma/Açma Fonksiyonu
async def toggle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str, lang_name: str):
    chat_id = update.effective_chat.id
    if chat_id not in DISABLED_LANGUAGES:
        DISABLED_LANGUAGES[chat_id] = set()

    if lang_code in DISABLED_LANGUAGES[chat_id]:
        DISABLED_LANGUAGES[chat_id].remove(lang_code)
        await update.effective_message.reply_text(f"✅ {lang_name} çevirisi bu grupta **AÇILDI**.")
    else:
        DISABLED_LANGUAGES[chat_id].add(lang_code)
        await update.effective_message.reply_text(f"❌ {lang_name} çevirisi bu grupta **KAPATILDI**.")


async def toggle_almanca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_language(update, context, "de", "Almanca")

async def toggle_rusca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_language(update, context, "ru", "Rusça")

async def toggle_turkce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_language(update, context, "tr", "Türkçe")

async def toggle_ingilizce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_language(update, context, "en", "İngilizce")


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

    # Otomatik Çeviri Kontrolü (Varsayılan Açık)
    if TRANSLATION_SETTINGS.get(chat_id, True):
        await handle_translation(message, text, chat_id)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Telegram hatası:", exc_info=context.error)


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Komut işleyicileri
    application.add_handler(CommandHandler("ceviri", toggle_translation))
    application.add_handler(CommandHandler("almanca", toggle_almanca))
    application.add_handler(CommandHandler("rusca", toggle_rusca))
    application.add_handler(CommandHandler("turkce", toggle_turkce))
    application.add_handler(CommandHandler("ingilizce", toggle_ingilizce))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)

    logger.info("Urfalı Harun Bot başlatılıyor...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
