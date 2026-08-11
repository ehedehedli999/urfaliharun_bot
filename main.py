import logging
import random
import re
import json
import time
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- TOKENLAR ---
TELEGRAM_TOKEN = "8363449973:AAEel1P8fp1b3eRhnbpDNM4Z6vdEbFQR8h0"
CEREBRAS_API_KEY = "csk-2nr3xkmt8x9eyfkc9hhc2nyrwf5nrx8kdt4pn8hwdjvewfxv"

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = "gpt-oss-120b"

USER_SCORES = {}
LANG_STATUS = {
    "tr": True,
    "ru": True,
    "de": True
}

# Kota (429) uyarısını gruba spam gibi göndermemek için son bildirim zamanı takibi
LAST_RATE_LIMIT_NOTICE = 0
RATE_LIMIT_NOTICE_COOLDOWN = 300  # saniye (5 dakika)

# Genel API hatası (401/400/500 vb.) bildirimi için aynı mantıkta ayrı bir zamanlayıcı
LAST_SERVICE_ERROR_NOTICE = 0
SERVICE_ERROR_NOTICE_COOLDOWN = 300  # saniye (5 dakika)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- TAM VE KESİNLİKLE EKSİKSİZ ÇEVİRİ PROMPTU (JSON ZORUNLU) ---
SYSTEM_TRANSLATE_PROMPT = """
You are a professional native-level translator for a multilingual Telegram community chat (Turkish, Russian, German speakers).

Translate the given short chat message the way a real native speaker would translate it in a casual conversation:
- Natural, idiomatic, and contextually correct.
- NOT a robotic word-for-word translation.
- NEVER invent, add, or drop meaning that isn't in the original message.
- Preserve tone (greeting, joke, slang, question, etc.) exactly as a native speaker would.

You MUST respond with STRICT JSON ONLY. No explanations, no markdown, no code fences, no extra text before or after the JSON.

Depending on the detected source language of the input, return exactly these keys:

If input is Turkish or Azerbaijani:
{"ru": "<Russian translation>", "de": "<German translation>"}

If input is Russian:
{"tr": "<Turkish translation>", "de": "<German translation>"}

If input is German:
{"tr": "<Turkish translation>", "ru": "<Russian translation>"}

MANDATORY RULES:
1. ALWAYS include BOTH required keys, even for very short messages like "Tmm", "Ok", "Selam", "Привет".
2. NEVER leave a value empty and NEVER omit a key.
3. Output ONLY the raw JSON object.
"""

COMMAND_3LANG_PROMPT = """
Sana verilen metni veya görevi 3 dilde (Türkçe, Rusça, Almanca) yanıtla.
Çıktı formatı KESİNLİKLE şöyle olmalı:
🇹🇷 [Türkçe İfade]
🇷🇺 [Rusça İfade - Kiril]
🇩🇪 [Almanca İfade]
"""

class RateLimitError(Exception):
    """Cerebras API kota/rate-limit (429) doldu."""
    pass

class TranslationServiceError(Exception):
    """Cerebras API'den 200 dışında bir yanıt geldi (key hatası, model hatası vb.)."""
    pass

async def query_grok(prompt: str, system_prompt: str, json_mode: bool = False) -> str:
    try:
        headers = {
            "Authorization": f"Bearer {CEREBRAS_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        data = {
            "model": CEREBRAS_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_completion_tokens": 300
        }
        if json_mode:
            # Cerebras'ın OpenAI uyumlu JSON modu: model artık saf JSON dışına çıkamaz
            data["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(CEREBRAS_URL, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            if response.status_code == 429:
                logger.error("Cerebras API kota/rate-limit doldu (429)")
                raise RateLimitError("Cerebras API kota doldu")
            # 200/429 dışındaki her durumda (401 geçersiz key, 400 hatalı istek, 500 vb.)
            # Render loglarında tam olarak neyin yanlış gittiğini görebilmek için
            # HTTP kodu + Cerebras'ın döndürdüğü hata mesajını eksiksiz yazdır.
            logger.error(f"Cerebras API hatası - HTTP {response.status_code}: {response.text}")
            raise TranslationServiceError(f"HTTP {response.status_code}: {response.text}")
    except (RateLimitError, TranslationServiceError):
        raise
    except httpx.TimeoutException:
        logger.error("Cerebras API isteği zaman aşımına uğradı (timeout)")
        raise TranslationServiceError("Zaman aşımı")
    except httpx.RequestError as e:
        logger.error(f"Cerebras API bağlantı hatası: {e}")
        raise TranslationServiceError(f"Bağlantı hatası: {e}")
    except Exception as e:
        logger.error(f"Beklenmeyen API hatası: {e}")
        raise TranslationServiceError(str(e))

def detect_language(text: str) -> str:
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    elif re.search(r'[äöüßÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo"]):
        return "de"
    else:
        return "tr"

LANG_FLAGS = {"tr": "🇹🇷", "ru": "🇷🇺", "de": "🇩🇪"}
REQUIRED_TARGETS = {
    "tr": ["ru", "de"],
    "ru": ["tr", "de"],
    "de": ["tr", "ru"],
}

SINGLE_LANG_NAMES = {"tr": "Turkish", "ru": "Russian", "de": "German"}

async def get_single_translation(clean_text: str, target: str) -> str:
    """
    JSON modu başarısız olursa devreye giren yedek yöntem.
    Tek bir dil için sade metin ister - modelin format bozma ihtimali çok daha düşük.
    """
    system_prompt = (
        f"You are a professional native-level translator. Translate the given short chat "
        f"message into natural, idiomatic {SINGLE_LANG_NAMES[target]}, the way a native "
        f"speaker would say it in a casual conversation. Respond with ONLY the translation "
        f"text - no quotes, no explanation, no extra text."
    )
    raw = await query_grok(f'Translate this message: "{clean_text}"', system_prompt)
    return raw.strip().strip('"') if raw else ""

async def get_translation(clean_text: str, src_lang: str, max_retries: int = 2) -> dict:
    """
    Kaynak dile göre gereken TÜM hedef dilleri JSON olarak ister.
    Bir dil eksik/boş gelirse (model saçmalarsa) otomatik tekrar dener.
    Eksiksiz sonuç gelene kadar (ya da deneme hakkı bitene kadar) devam eder.
    JSON denemeleri tamamen başarısız olursa, dilleri tek tek çevirerek yedek devreye girer
    (kısa/argo mesajlarda model JSON formatını bozabiliyor, bu tamamen sessiz kalmayı önler).
    """
    targets = REQUIRED_TARGETS.get(src_lang, [])
    if not targets:
        return {}

    for _ in range(max_retries + 1):
        raw = await query_grok(
            f'Translate this chat message: "{clean_text}"',
            SYSTEM_TRANSLATE_PROMPT,
            json_mode=True,
        )
        if not raw:
            continue

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            continue

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue

        # Gerekli TÜM diller dolu geldi mi kontrol et; biri bile eksikse tekrar dene
        if all(str(data.get(t, "")).strip() for t in targets):
            return {t: str(data[t]).strip() for t in targets}

    # JSON yöntemi tüm denemelerde başarısız oldu -> yedek yönteme geç (dilleri tek tek çevir)
    logger.warning(f"JSON çeviri başarısız, yedek yönteme geçiliyor: '{clean_text}'")
    result = {}
    for t in targets:
        translated = await get_single_translation(clean_text, t)
        if translated:
            result[t] = translated
    return result

def add_point(chat_id: int, user):
    if user.is_bot: return
    if chat_id not in USER_SCORES: USER_SCORES[chat_id] = {}
    uid = user.id
    if uid not in USER_SCORES[chat_id]:
        USER_SCORES[chat_id][uid] = {"name": user.first_name, "points": 0, "messages": 0}
    USER_SCORES[chat_id][uid]["points"] += random.randint(5, 15)
    USER_SCORES[chat_id][uid]["messages"] += 1
    USER_SCORES[chat_id][uid]["name"] = user.first_name

# --- DİL AÇMA / KAPATMA KOMUTLARI ---
async def cmd_toggle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    cmd = update.message.text.split()[0].replace("/", "").split("@")[0].lower()
    
    if cmd == "turkce":
        LANG_STATUS["tr"] = not LANG_STATUS["tr"]
        st = "AÇILDI ✅" if LANG_STATUS["tr"] else "KAPATILDI ❌"
        msg = f"🇹🇷 Türkçe Çeviri: {st}"
    elif cmd == "rusca":
        LANG_STATUS["ru"] = not LANG_STATUS["ru"]
        st = "AÇILDI ✅" if LANG_STATUS["ru"] else "KAPATILDI ❌"
        msg = f"🇷🇺 Rusça Çeviri: {st}"
    elif cmd == "almanca":
        LANG_STATUS["de"] = not LANG_STATUS["de"]
        st = "AÇILDI ✅" if LANG_STATUS["de"] else "KAPATILDI ❌"
        msg = f"🇩🇪 Almanca Çeviri: {st}"
    else:
        return
        
    await update.message.reply_text(msg)

# --- EĞLENCE KOMUTLARI ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = "Hakkımda metni yaz: Ben Viyana Ai Yapay zeka botuyum. Ehed tarafından tasarlandım."
        ans = await query_grok(p, COMMAND_3LANG_PROMPT)
        if ans: await update.message.reply_text(ans)
    except Exception as e:
        logger.error(f"/help hatası: {e}")

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = " ".join(context.args) if context.args else "genel"
        p = f"Kullanıcı için ({args}) burcu/fal hakkında eğlenceli ve kısa bir yorum yap."
        ans = await query_grok(p, COMMAND_3LANG_PROMPT)
        if ans: await update.message.reply_text(ans)
    except Exception as e:
        logger.error(f"/burc hatası: {e}")

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user.first_name
        p = f"Günün Kralı ilan edilen kişi: {user}. Onun için kısa bir övgü fermanı yaz."
        ans = await query_grok(p, COMMAND_3LANG_PROMPT)
        if ans: await update.message.reply_text(ans)
    except Exception as e:
        logger.error(f"/kral hatası: {e}")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🇹🇷 Henüz puan yok!\n🇷🇺 Пока нет очков!\n🇩🇪 Noch keine Punkte!")
        return
    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:5]
    text = "🏆 **PUAN SIRALAMASI / РЕЙТИНГ / RANGLISTE** 🏆\n\n"
    for idx, u in enumerate(sorted_users, 1):
        text += f"{idx}. **{u['name']}** — {u['points']} Pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- MESAJ İŞLEYİCİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        if not message or not message.text: return
        text = message.text.strip()
        chat_id = message.chat_id
        user = update.effective_user

        if user.is_bot or text.startswith("/"): return

        add_point(chat_id, user)

        clean_text = re.sub(r'@\w+', '', text).strip()
        words = clean_text.split()
        if len(words) < 1 or "http" in text: return

        src_lang = detect_language(clean_text)
        translations = await get_translation(clean_text, src_lang)

        if not translations: return

        valid_lines = []
        for target in REQUIRED_TARGETS.get(src_lang, []):
            if not LANG_STATUS.get(target, True):
                continue  # Bu dil komutla kapatılmış
            text_t = translations.get(target)
            if text_t:
                valid_lines.append(f"{LANG_FLAGS[target]} {text_t}")

        if valid_lines:
            final_output = "\n".join(valid_lines)
            await message.reply_text(final_output)

    except RateLimitError:
        global LAST_RATE_LIMIT_NOTICE
        now = time.time()
        if now - LAST_RATE_LIMIT_NOTICE > RATE_LIMIT_NOTICE_COOLDOWN:
            LAST_RATE_LIMIT_NOTICE = now
            try:
                await update.effective_message.reply_text(
                    "⚠️ Çeviri servisi şu anda günlük/dakikalık kota limitine ulaştı. "
                    "Kota yenilenene kadar çeviriler geçici olarak çalışmayabilir."
                )
            except Exception as notify_err:
                logger.error(f"Kota bildirimi gönderilemedi: {notify_err}")

    except TranslationServiceError as e:
        global LAST_SERVICE_ERROR_NOTICE
        logger.error(f"Çeviri servisi hatası (kullanıcıya bildiriliyor): {e}")
        now = time.time()
        if now - LAST_SERVICE_ERROR_NOTICE > SERVICE_ERROR_NOTICE_COOLDOWN:
            LAST_SERVICE_ERROR_NOTICE = now
            try:
                await update.effective_message.reply_text(
                    "⚠️ Çeviri servisine şu anda ulaşılamıyor. Render loglarını kontrol edin, "
                    "sorun devam ederse API key'i doğrulayın."
                )
            except Exception as notify_err:
                logger.error(f"Servis hatası bildirimi gönderilemedi: {notify_err}")

    except Exception as e:
        logger.error(f"Handle error: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler(["turkce", "rusca", "almanca"], cmd_toggle_lang))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("burc", cmd_burc))
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler(["siralama", "sirallama", "puan"], cmd_siralama))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Viyana AI Güncellenmiş Kod İle Yayında...")
    app.run_polling(drop_pending_updates=True)

