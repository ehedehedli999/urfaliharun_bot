import os
import re
import logging 

from telegram import Update
from telegram.ext import (
ApplicationBuilder,
ContextTypes,
MessageHandler,
filters,
) 

from openai import OpenAI


=========================================================
LOGGING
========================================================= 

logging.basicConfig(
format="%(asctime)s - %(levelname)s - %(message)s",
level=logging.INFO,
) 

logger = logging.getLogger(name)


=========================================================
ENVIRONMENT
========================================================= 

TELEGRAM_BOT_TOKEN = os.environ.get"8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM"
GROQ_API_KEY = os.environ.get"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"


=========================================================
GROQ MODEL
========================================================= 

GROQ_MODEL = "qwen/qwen3.6-27b"


=========================================================
TRANSLATION SYSTEM PROMPT
========================================================= 

SYSTEM_PROMPT = """
Sen Viyana AI adlı profesyonel otomatik çeviri botusun. 

GÖREVİN SADECE ÇEVİRİ YAPMAKTIR. 

Gelen mesajın dilini otomatik olarak tespit et. 

DESTEKLENEN HEDEF DİLLER:
• Türkçe
• Almanca
• Rusça 

DİL KURALLARI: 

1. Kullanıcı TÜRKÇE yazarsa:
Sadece Almanca ve Rusçaya çevir. 

Çıktı:
🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]


2. Kullanıcı ALMANCA yazarsa:
Sadece Türkçe ve Rusçaya çevir. 

Çıktı:
🇹🇷 Türkçe: [çeviri]
🇷🇺 Rusça: [çeviri]


3. Kullanıcı RUSÇA yazarsa:
Sadece Türkçe ve Almancaya çevir. 

Çıktı:
🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]


4. Kullanıcı İNGİLİZCE, AZERBAYCANCA veya başka bir dilde yazarsa:
Sadece Türkçe, Almanca ve Rusçaya çevir. 

Çıktı:
🇹🇷 Türkçe: [çeviri]
🇩🇪 Almanca: [çeviri]
🇷🇺 Rusça: [çeviri]


ÇEVİRİ KALİTESİ: 

• Çeviri C2 seviyesinde olmalıdır.
• Hedef dilin ana dili olan bir insan tarafından yazılmış gibi doğal olmalıdır.
• Anlam kesinlikle korunmalıdır.
• Kullanıcının söylemediği hiçbir şeyi ekleme.
• Cümleye yeni anlam katma.
• Tahmin yapma.
• Uydurma kelime veya ifade oluşturma.
• Açıklama ekleme.
• Yorum ekleme.
• Özetleme yapma.
• Mesajı genişletme.
• Mesajı kısaltma.
• Kullanıcının duygusunu ve tonunu koru.
• Argo varsa hedef dilde doğal karşılığını kullan.
• Deyim varsa hedef dildeki en doğal eşdeğerini kullan.
• Küfür varsa anlamını koru.
• Mizah varsa mümkün olduğunca koru.
• Özel isimleri gereksiz yere çevirme.
• Sayıları, tarihleri ve önemli bilgileri değiştirme. 

ÇOK KISA MESAJLAR DA ÇEVRİLECEK. 

Örneğin:
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

gibi tek kelimelik veya çok kısa mesajları ASLA görmezden gelme.
Bunları da mutlaka hedef dillere çevir. 

ÇIKTI KURALI: 

Sadece yukarıda belirtilen çeviri formatını kullan. 

Kesinlikle şunları yazma:
• <think>
• </think>
• reasoning
• analysis
• düşünme süreci
• açıklama
• yorum
• "İşte çeviri"
• "Tabii"
• "Elbette"
• "Here is the translation"
• başka herhangi bir ek metin 

Kullanıcının mesajını analiz ettiğini söyleme. 

Sadece nihai çevirileri gönder. 

ÇEVİRİYİ BİREBİR ANLAM KORUYARAK YAP.
"""


=========================================================
THINK / REASONING TEMİZLEME
========================================================= 

def clean_response(text: str) -> str:
"""
Model yanlışlıkla <think> veya benzeri reasoning
çıktısı üretirse Telegram'a göndermeden temizler.
""" 

if not text:
return "" 

# <think>...</think> bloklarını sil
text = re.sub(
r"<think>.*?</think>",
"",
text,
flags=re.DOTALL | re.IGNORECASE,
) 

# Tek başına kalan think etiketlerini de sil
text = re.sub(
r"</?think>",
"",
text,
flags=re.IGNORECASE,
) 

# Bazı reasoning etiketleri
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


=========================================================
GROQ TRANSLATION
========================================================= 

def translate_with_groq(text: str) -> str: 

if not GROQ_API_KEY:
return "⚠️ Xəta: GROQ_API_KEY tapılmadı!" 

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

# Çeviri için düşük sıcaklık:
# daha tutarlı ve daha az uydurma
temperature=0.2, 

max_tokens=1000, 

# Qwen'in reasoning çıktısını gizle
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

return (
"⚠️ Tərcümə xətası: "
f"{str(e)}"
)


=========================================================
TELEGRAM MESSAGE HANDLER
========================================================= 

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

# Komutları çevirme
if text.startswith("/"):
return 

if not text:
return 

translated = translate_with_groq(text) 

await message.reply_text(
translated,
disable_web_page_preview=True,
)


=========================================================
ERROR HANDLER
========================================================= 

async def error_handler(
update: object,
context: ContextTypes.DEFAULT_TYPE,
): 

logger.error(
"Telegram xətası: %s",
context.error,
)


=========================================================
MAIN
========================================================= 

def main(): 

if not TELEGRAM_BOT_TOKEN:
raise RuntimeError(
"TELEGRAM_BOT_TOKEN tapılmadı!"
) 

if not GROQ_API_KEY:
raise RuntimeError(
"GROQ_API_KEY tapılmadı!"
) 

app = (
ApplicationBuilder()
.token(TELEGRAM_BOT_TOKEN)
.build()
) 

app.add_handler(
MessageHandler(
filters.TEXT & ~filters.COMMAND,
handle_message,
)
) 

app.add_error_handler(error_handler) 

logger.info(
"🤖 VIYANA AI TƏRCÜMƏ BOTU HAZIRDIR!"
) 

app.run_polling(
drop_pending_updates=True
)


=========================================================
START
========================================================= 

if name == "main":
main()
