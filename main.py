import logging
import re
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = "8363449973:AAEel1P8fp1b3eRhnbpDNM4Z6vdEbFQR8h0"
XAI_API_KEY = "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"
XAI_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- YENİ SİSTEM: %100 ÇEVİRİ MAKİNESİ ---
SYSTEM_PROMPT = """
Sen bir çeviri makinesisin. Sohbet etme, yorum yapma, cevap verme.
Görevin: Girdi metnini belirtilen iki dile çevir.
ÇIKTI FORMATI: SADECE 'Çeviri1|Çeviri2' formatında çıktı ver.
ASLA başlık, açıklama veya orijinal metni ekleme.
"""

async def get_translation(text, source_lang):
    # Dilleri belirle
    if source_lang == "tr":
        target_info = [("Rusça", "Almanca"), ("🇷🇺", "🇩🇪")]
    elif source_lang == "ru":
        target_info = [("Türkçe", "Almanca"), ("🇹🇷", "🇩🇪")]
    else: # Almanca ise
        target_info = [("Türkçe", "Rusça"), ("🇹🇷", "🇷🇺")]
    
    prompt = f"'{text}' metnini {target_info[0][0]} ve {target_info[0][1]} dillerine çevir. Format: Cevap1|Cevap2"
    
    try:
        headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
        # Temperature 0: AI'nın yaratıcılığını tamamen öldürdük, robot gibi çalışacak.
        data = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "temperature": 0.0}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(XAI_URL, headers=headers, json=data)
            content = resp.json()['choices'][0]['message']['content'].strip()
            
            # Formatı parçala
            if '|' in content:
                parts = content.split('|')
                return f"{target_info[1][0]} {parts[0].strip()}\n{target_info[1][1]} {parts[1].strip()}"
            return None # Format bozuksa çeviri yapma
    except:
        return None

def detect_language(text):
    if re.search(r'[\u0400-\u04FF]', text): return "ru"
    if re.search(r'[äöüßäÖÜß]|ich|und|ist|die|der', text.lower()): return "de"
    return "tr"

async def handle_message(update, context):
    text = update.message.text
    if not text or text.startswith("/"): return
    
    # 3 kelimeden az veya çok saçma mesajları çevirme
    if len(text.split()) < 2: return

    lang = detect_language(text)
    translation = await get_translation(text, lang)
    
    if translation:
        await update.message.reply_text(translation)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot şimdi 'Makine Modu'nda çalışıyor.")
    app.run_polling()
