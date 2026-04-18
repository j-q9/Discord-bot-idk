import discord
from discord.ext import commands
import asyncio
import json
import re
import os
from datetime import datetime, timedelta, timezone
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp
import random

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ============================================================
# KEEP ALIVE
# ============================================================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, *args):
        pass

def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()

Thread(target=keep_alive, daemon=True).start()

# ============================================================
# CONFIG
# ============================================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
PREFIX = "!"
ROLL_CHANNEL_ID = 1490276530452955246
ROLL_MIN = 1
ROLL_MAX = 350

# ============================================================
# INTENTS
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ============================================================
# STATE
# ============================================================
quiz_active = {}
vquiz_active = {}
roll_cooldown = {}
wordchain_games = {}

# ============================================================
# FREE DICTIONARY CHECK
# ============================================================
async def is_valid_word(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return r.status == 200

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print("Bot ready")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id

    # ================= WORDCHAIN =================
    if uid in wordchain_games:
        game = wordchain_games[uid]

        if message.content.lower() == "!end":
            del wordchain_games[uid]
            await message.reply("Game ended.")
            return

        user_word = message.content.lower()

        if not user_word.isalpha():
            await message.reply("❌ Only letters allowed")
            return

        if not await is_valid_word(user_word):
            await message.reply("❌ Not a real English word")
            return

        if user_word in game["used"]:
            await message.reply("❌ Already used")
            return

        if not user_word.startswith(game["last_letter"]):
            await message.reply(f"❌ Must start with '{game['last_letter']}'")
            return

        game["used"].add(user_word)

        # bot tries random words until valid
        for _ in range(50):
            candidate = random.choice(["apple","tiger","rat","tree","egg","grape","rose","sun","night","tea"])
            if candidate not in game["used"] and candidate.startswith(user_word[-1]):
                bot_word = candidate
                break
        else:
            del wordchain_games[uid]
            await message.reply("🎉 You win! No words left.")
            return

        game["used"].add(bot_word)
        game["last_letter"] = bot_word[-1]

        await message.reply(bot_word)
        return

    # ================= ROLL =================
    if message.guild and message.channel.id == ROLL_CHANNEL_ID:
        if re.match(r"^\d+$", message.content):
            now = utcnow()
            last = roll_cooldown.get(message.author.id)

            if last and (now - last).total_seconds() < 3:
                return

            roll_cooldown[message.author.id] = now

            num = int(message.content)
            if ROLL_MIN <= num <= ROLL_MAX:
                if random.random() < 0.01:
                    await message.reply("🎉 You won!")
                else:
                    await message.reply("❌ Try again")
                return

    # ================= QUIZ =================
    ch = message.channel.id

    if ch in quiz_active and ch not in vquiz_active:
        if message.content.lower() == quiz_active[ch]["answer"]:
            await message.reply("Correct")
            del quiz_active[ch]
        return

    elif ch in vquiz_active:
        if message.content.lower() in vquiz_active[ch]["answers"]:
            await message.reply("Correct")
            del vquiz_active[ch]
        return

    await bot.process_commands(message)

# ============================================================
# COMMANDS
# ============================================================

@bot.command()
async def game(ctx):
    await ctx.send("🎮 Available Games:\n• !wordchain")

@bot.command()
async def wordchain(ctx):
    start = random.choice(["apple","tiger","rose","night","tea"])
    wordchain_games[ctx.author.id] = {
        "last_letter": start[-1],
        "used": set([start])
    }
    await ctx.send(f"Start word: **{start}**\nNext must start with '{start[-1]}'")

@bot.command()
async def end(ctx):
    if ctx.author.id in wordchain_games:
        del wordchain_games[ctx.author.id]
        await ctx.send("Game ended.")

@bot.command()
async def ai(ctx, *, text):
    await ctx.reply("AI disabled.")

@bot.command()
async def quiz(ctx):
    quiz_active[ctx.channel.id] = {"answer":"42"}
    await ctx.send("What is answer?")

@bot.command()
async def vquiz(ctx):
    vquiz_active[ctx.channel.id] = {"answers":["cat"]}
    await ctx.send("Guess image")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong")

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)