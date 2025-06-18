
import logging
import phonenumbers
from phonenumbers import geocoder, carrier
import socket
import dns.resolver
import urllib.parse
import aiohttp
import asyncio
import os
import csv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

TOKEN = os.getenv("TOKEN", "PASTE_YOUR_TOKEN_HERE")
IPINFO_TOKEN = "85f0b89ca3f36b"
HUNTER_API_KEY = "f099202c6f4246b57954f5fd54e636892bffaac6"
HIBP_API_KEY = "YOUR_HIBP_API_KEY"
CSV_FOLDER = "csv_data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я OSINT-бот.
Выбери команду:
"
        "/phone, /ip, /domain, /email, /hibp, /telegram, /telegramid, /searchcsv, /listcsv"
    )

async def cmd_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_phone"
    await update.message.reply_text("📞 Введите номер телефона:")

async def cmd_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_ip"
    await update.message.reply_text("🌍 Введите IP-адрес:")

async def cmd_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_domain"
    await update.message.reply_text("🌐 Введите домен:")

async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_email"
    await update.message.reply_text("📧 Введите email:")

async def cmd_hibp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_hibp"
    await update.message.reply_text("🕵️ Введите email для HIBP:")

async def cmd_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_telegram"
    await update.message.reply_text("🔍 Введите Telegram username (@user):")

async def cmd_telegramid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_telegramid"
    await update.message.reply_text("🆔 Введите Telegram ID:")

async def cmd_searchcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "awaiting_csv"
    await update.message.reply_text("📂 Введите ключевое слово для поиска в CSV:")

async def cmd_listcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = [f for f in os.listdir(CSV_FOLDER) if f.endswith(".csv")]
    if files:
        await update.message.reply_text("📁 CSV-файлы:
" + "
".join(files))
    else:
        await update.message.reply_text("❌ Нет CSV-файлов.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    text = update.message.text.strip()

    if state == "awaiting_phone":
        try:
            num = phonenumbers.parse(text, None)
            country = geocoder.description_for_number(num, "en")
            operator = carrier.name_for_number(num, "en")
            await update.message.reply_text(f"📞 Страна: {country}
📡 Оператор: {operator}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    elif state == "awaiting_ip":
        url = f"https://ipinfo.io/{text}?token={IPINFO_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                result = "
".join(f"{k}: {v}" for k, v in data.items())
                await update.message.reply_text(result)

    elif state == "awaiting_domain":
        try:
            ip = socket.gethostbyname(text)
            answers = dns.resolver.resolve(text, 'NS')
            ns = ", ".join(str(r.target) for r in answers)
            await update.message.reply_text(f"🌐 IP: {ip}
🧭 NS: {ns}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    elif state == "awaiting_email":
        url = f"https://api.hunter.io/v2/email-verifier?email={text}&api_key={HUNTER_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                result = data.get("data", {})
                reply = "
".join(f"{k}: {v}" for k, v in result.items())
                await update.message.reply_text(reply)

    elif state == "awaiting_hibp":
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{text}"
        headers = {
            "hibp-api-key": HIBP_API_KEY,
            "User-Agent": "TelegramOSINTBot"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    await update.message.reply_text("✅ Утечек не найдено")
                elif resp.status == 200:
                    breaches = await resp.json()
                    names = ", ".join(b["Name"] for b in breaches)
                    await update.message.reply_text(f"⚠️ Утечки найдены: {names}")
                else:
                    await update.message.reply_text(f"❌ Ошибка HIBP: {resp.status}")

    elif state == "awaiting_telegram":
        username = text.lstrip("@")
        await update.message.reply_text(f"🔗 Проверь: https://t.me/{username}")

    elif state in ("awaiting_telegramid", "awaiting_csv"):
        results = search_in_csv(text)
        for result in results:
            await update.message.reply_text(result)

    else:
        await update.message.reply_text("🤖 Напишите команду типа /phone")

    user_states.pop(user_id, None)

def search_in_csv(keyword):
    results = []
    keyword = keyword.lower()
    for file in os.listdir(CSV_FOLDER):
        if file.endswith(".csv"):
            try:
                with open(os.path.join(CSV_FOLDER, file), encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if any(keyword in str(cell).lower() for cell in row):
                            results.append(f"[{file}]: {' | '.join(row)}")
                            if len(results) >= 20:
                                return results
            except Exception as e:
                results.append(f"[{file}] Ошибка: {e}")
    return results or ["❌ Ничего не найдено"]

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("phone", cmd_phone))
    app.add_handler(CommandHandler("ip", cmd_ip))
    app.add_handler(CommandHandler("domain", cmd_domain))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("hibp", cmd_hibp))
    app.add_handler(CommandHandler("telegram", cmd_telegram))
    app.add_handler(CommandHandler("telegramid", cmd_telegramid))
    app.add_handler(CommandHandler("searchcsv", cmd_searchcsv))
    app.add_handler(CommandHandler("listcsv", cmd_listcsv))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ OSINT-бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
