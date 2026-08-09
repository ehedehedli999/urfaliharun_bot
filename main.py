import os
import logging
import urllib.parse
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)


# =========================================================
# LOG AYARLARI
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# ENV DEĞİŞKENLERİ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# =========================================================
# OPENROUTER AYARLARI
# =========================================================

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ÖNEMLİ:
# Eski modelleri kaldırdık.
# OpenRouter mevcut ücretsiz modellerden otomatik seçim yapacak.
OPENROUTER_MODEL = "openrouter/free"


# =========================================================
# HERMANAKI AI SİSTEM PROMPTU
# =========================================================

HERMANAKI_SYSTEM_PROMPT = (
    "Sen Hermanaki adında zeki, kültürlü, akıcı ve C1 seviyesinde "
    "dil hakimiyetine sahip üst düzey bir yapay zeka asistanısın. "

    "Türkçe, Azerbaycanca, Rusça ve Almanca dillerine çok iyi hakimsin. "

    "Sana sorulan sorulara C1 kalitesinde, net, doğal, insan gibi "
    "ve doğrudan cevap ver. "

    "Kullanıcının kullandığı dile mümkün olduğunca aynı dilde cevap ver. "

    "Gereksiz yere 'Nasıl yardımcı olabilirim?', "
    "'Başka sorunuz var mı?' gibi takip soruları sorma. "

    "Kullanıcı ne istiyorsa doğrudan onu yap."
)


# =========================================================
# ÇEVİRİ PROMPTU
# =========================================================

TRANSLATE_PROMPT = (
    "Sen C1 ve üstü seviyede profesyonel bir çevirmensin. "

    "Sana gelen metnin anlamını, tonunu, duygusunu ve doğallığını "
    "bozmadan Türkçe, Rusça ve Almancaya çevir. "

    "Başka hiçbir açıklama ekleme. "

    "Yanıtını tam olarak şu formatta ver:\n\n"

    "Türkçe: [çeviri]\n"
    "Rusça: [çeviri]\n"
    "Almanca: [çeviri]"
)


# =========================================================
# TELEGRAM UZUN MESAJ GÖNDERME
# =========================================================

async def send_long_message(message, text):
    """
    Telegram mesajları çok uzun olduğunda 4096 karakter sınırına
    takılmamak için mesajı parçalara böler.
    """

    if not text:
        return

    max_length = 4000

    for i in range(0, len(text), max_length):
        part = text[i:i + max_length]
        await message.reply_text(part)


# =========================================================
# OPENROUTER AI
# =========================================================

def query_openrouter(prompt: str, system_prompt: str) -> str:
    """
    OpenRouter üzerinden AI cevabı alır.
    """

    if not OPENROUTER_API_KEY:
        raise Exception(
            "OPENROUTER_API_KEY bulunamadı. "
            "Render Environment Variables bölümünü kontrol et."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",

        # OpenRouter için isteğe bağlı bilgiler
        "HTTP-Referer": "https://t.me/",
        "X-Title": "Hermanaki AI Bot",
    }

    data = {
        "model": OPENROUTER_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        # Çok uzamasın
        "max_tokens": 2000,

        # Biraz doğal cevaplar
        "temperature": 0.7,
    }

    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=data,
            timeout=60,
        )

    except requests.exceptions.Timeout:
        raise Exception(
            "OpenRouter bağlantısı zaman aşımına uğradı."
        )

    except requests.exceptions.ConnectionError:
        raise Exception(
            "OpenRouter sunucusuna bağlanılamadı."
        )

    except Exception as e:
        raise Exception(
            f"Bağlantı hatası: {str(e)}"
        )

    # -----------------------------------------------------
    # BAŞARILI
    # -----------------------------------------------------

    if response.status_code == 200:

        try:
            result = response.json()

        except Exception:
            raise Exception(
                "OpenRouter geçersiz JSON cevabı döndürdü."
            )

        choices = result.get("choices")

        if not choices:
            raise Exception(
                f"OpenRouter boş cevap döndürdü: {result}"
            )

        message_data = choices[0].get("message", {})

        content = message_data.get("content")

        if content:
            return content.strip()

        raise Exception(
            f"AI cevabı bulunamadı: {result}"
        )

    # -----------------------------------------------------
    # HATA
    # -----------------------------------------------------

    error_text = response.text

    try:
        error_json = response.json()

        if isinstance(error_json, dict):
            error_object = error_json.get("error", {})

            if isinstance(error_object, dict):
                error_message = error_object.get("message")

                if error_message:
                    error_text = error_message

    except Exception:
        pass

    if response.status_code == 401:
        raise Exception(
            "OpenRouter API anahtarı geçersiz. "
            "OPENROUTER_API_KEY değerini kontrol et."
        )

    if response.status_code == 403:
        raise Exception(
            "OpenRouter API erişimi reddedildi. "
            "API anahtarının durumunu kontrol et."
        )

    if response.status_code == 404:
        raise Exception(
            "OpenRouter model endpoint'i bulunamadı. "
            "Kod artık openrouter/free kullanıyor; "
            "Render'ın yeni kodu çalıştırdığından emin ol."
        )

    if response.status_code == 429:
        raise Exception(
            "OpenRouter ücretsiz kullanım limiti aşıldı "
            "veya çok fazla istek gönderildi. Biraz bekleyip tekrar dene."
        )

    raise Exception(
        f"OpenRouter HTTP {response.status_code}: {error_text}"
    )


# =========================================================
# /START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        "🤖 Hermanaki AI aktif!\n\n"
        "💬 Bana @bot_adı şeklinde yazabilirsin.\n"
        "↩️ Mesajıma reply yaparak da konuşabilirsin.\n\n"
        "🎨 Resim oluşturmak için:\n"
        "/ciz uzayda yürüyen kedi\n\n"
        "🌐 Normal mesajlarda Türkçe / Rusça / Almanca "
        "çeviri sistemi çalışır."
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        "🤖 Hermanaki AI Komutları\n\n"
        "/start - Botu başlat\n"
        "/help - Yardım\n"
        "/ciz <metin> - Resim oluştur\n"
        "/resim <metin> - Resim oluştur\n\n"
        "💬 AI ile konuşmak için:\n"
        "@bot_adı merhaba\n\n"
        "veya botun mesajına reply yap."
    )


# =========================================================
# /CIZ VE /RESIM
# =========================================================

async def draw_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    prompt = " ".join(context.args).strip()

    if not prompt:

        await message.reply_text(
            "🎨 Lütfen oluşturmak istediğin resmi yaz.\n\n"
            "Örnek:\n"
            "/ciz gece şehirde yürüyen siyah kurt"
        )

        return

    await generate_and_send_image(
        message,
        prompt
    )


# =========================================================
# RESİM OLUŞTURMA
# =========================================================

async def generate_and_send_image(
    message,
    prompt: str
):

    status_msg = None

    try:

        status_msg = await message.reply_text(
            "🎨 Görsel hazırlanıyor...\n"
            "⏳ Lütfen bekle."
        )

        encoded_prompt = urllib.parse.quote(
            prompt,
            safe=""
        )

        image_url = (
            "https://image.pollinations.ai/prompt/"
            f"{encoded_prompt}"
            "?width=1024"
            "&height=1024"
            "&nologo=true"
        )

        await message.reply_photo(
            photo=image_url,
            caption=f"🖼 {prompt}"
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:

        logger.error(
            f"Resim oluşturma hatası: {e}"
        )

        if status_msg:

            try:

                await status_msg.edit_text(
                    "⚠️ Görsel oluşturulurken hata oluştu.\n\n"
                    f"Hata: {str(e)}"
                )

            except Exception:
                pass


# =========================================================
# MESAJ İŞLEYİCİ
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    if not message.text:
        return

    text = message.text.strip()

    if not text:
        return

    # -----------------------------------------------------
    # BOT KULLANICI ADI
    # -----------------------------------------------------

    bot_username = context.bot.username

    if not bot_username:
        bot_username = ""


    # -----------------------------------------------------
    # RESİM KOMUTU
    # -----------------------------------------------------

    lower_text = text.lower()

    if lower_text.startswith("resim çiz"):

        prompt = text[len("resim çiz"):].strip()

        if prompt:

            await generate_and_send_image(
                message,
                prompt
            )

        else:

            await message.reply_text(
                "🎨 Örnek:\n"
                "resim çiz uzayda yürüyen kurt"
            )

        return


    if lower_text.startswith("görsel çiz"):

        prompt = text[len("görsel çiz"):].strip()

        if prompt:

            await generate_and_send_image(
                message,
                prompt
            )

        else:

            await message.reply_text(
                "🎨 Örnek:\n"
                "görsel çiz gece İstanbul"
            )

        return


    # -----------------------------------------------------
    # OPENROUTER API KONTROLÜ
    # -----------------------------------------------------

    if not OPENROUTER_API_KEY:

        await message.reply_text(
            "⚠️ AI Hatası:\n\n"
            "OPENROUTER_API_KEY Render'a eklenmemiş."
        )

        return


    # -----------------------------------------------------
    # BOT MENTION KONTROLÜ
    # -----------------------------------------------------

    is_mentioned = False

    if bot_username:

        # @botusername şeklinde yazılmış mı?
        if f"@{bot_username}".lower() in lower_text:

            is_mentioned = True


    # Telegram entity kontrolü

    if message.entities:

        for entity in message.entities:

            if entity.type == "mention":

                try:

                    mention_text = text[
                        entity.offset:
                        entity.offset + entity.length
                    ]

                    if mention_text.lower() == (
                        f"@{bot_username}".lower()
                    ):

                        is_mentioned = True

                except Exception:

                    pass


    # -----------------------------------------------------
    # BOT MESAJINA REPLY MI?
    # -----------------------------------------------------

    is_reply_to_bot = False

    if message.reply_to_message:

        replied_message = message.reply_to_message

        if replied_message.from_user:

            if replied_message.from_user.id == context.bot.id:

                is_reply_to_bot = True


    # -----------------------------------------------------
    # MENTION TEMİZLE
    # -----------------------------------------------------

    clean_text = text

    if bot_username:

        clean_text = clean_text.replace(
            f"@{bot_username}",
            ""
        ).strip()


    # =====================================================
    # AI MODU
    # =====================================================

    if is_mentioned or is_reply_to_bot:

        try:

            if not clean_text:

                clean_text = "Merhaba"

            await message.chat.send_action(
                action="typing"
            )

            reply = query_openrouter(
                clean_text,
                HERMANAKI_SYSTEM_PROMPT
            )

            await send_long_message(
                message,
                reply
            )

        except Exception as e:

            logger.error(
                f"Hermanaki AI hatası: {e}"
            )

            await message.reply_text(
                "⚠️ AI Hatası:\n\n"
                f"{str(e)}"
            )

        return


    # =====================================================
    # ÇEVİRİ MODU
    # =====================================================

    try:

        await message.chat.send_action(
            action="typing"
        )

        reply = query_openrouter(
            text,
            TRANSLATE_PROMPT
        )

        await send_long_message(
            message,
            reply
        )

    except Exception as e:

        logger.error(
            f"Hermanaki Çeviri hatası: {e}"
        )

        await message.reply_text(
            "⚠️ Çeviri Hatası:\n\n"
            f"{str(e)}"
        )


# =========================================================
# HATA YAKALAMA
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram bot hatası:",
        exc_info=context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # TOKEN KONTROL
    # -----------------------------------------------------

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_TOKEN bulunamadı!"
        )


    if not OPENROUTER_API_KEY:

        logger.warning(
            "OPENROUTER_API_KEY bulunamadı. "
            "AI özellikleri çalışmayacak."
        )


    # -----------------------------------------------------
    # TELEGRAM APPLICATION
    # -----------------------------------------------------

    application = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )


    # -----------------------------------------------------
    # KOMUTLAR
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            ["ciz", "resim"],
            draw_command
        )
    )


    # -----------------------------------------------------
    # NORMAL MESAJLAR
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )


    # -----------------------------------------------------
    # HATA HANDLER
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )


    # -----------------------------------------------------
    # BAŞLAT
    # -----------------------------------------------------

    logger.info(
        "🤖 Hermanaki AI Botu başlatılıyor..."
    )

    logger.info(
        "🧠 OpenRouter modeli: %s",
        OPENROUTER_MODEL
    )

    logger.info(
        "🎨 Resim sistemi aktif."
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# PROGRAM BAŞLANGICI
# =========================================================

if __name__ == "__main__":
    main()
