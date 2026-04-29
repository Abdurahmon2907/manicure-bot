from flask import Flask, request
from aiogram import Bot, Dispatcher
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

# Обработка сообщений
@dp.message()
async def echo(message):
    await message.answer(f"You said: {message.text}")

# webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dp.feed_raw_update(bot, update))

    return "ok"

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))