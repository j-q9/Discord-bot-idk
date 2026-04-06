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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PREFIX = "!"
COOLDOWN_SECONDS = 5
ADMIN_ROLES = ["Owner", "Management"]
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
user_last_called = {}
conversation_history = {}
user_points = {}
quiz_active = {}
vquiz_active = {}
warn_records = {}
roll_cooldown = {}

# ============================================================
# HELPERS
# ============================================================
def has_admin_role(member):
    return member.guild.owner_id == member.id or any(r.name in ADMIN_ROLES for r in member.roles)

def is_roll_channel(channel):
    return channel.id == ROLL_CHANNEL_ID

def extract_json_action(text):
    try:
        return json.loads(text) if text.strip().startswith("{") else None
    except:
        return None

def clean_ai_reply(text):
    return re.sub(r'\{.*\}', '', text, flags=re.DOTALL).strip()

# ============================================================
# AI
# ============================================================
MEMBER_PROMPT = "You are a friendly Discord assistant. Short replies."

ADMIN_PROMPT = """You are a Discord manager.
If action needed → ONLY return JSON.
NO TEXT with JSON.

Example:
{"action":"ban_member","data":{"user_id":"123","reason":"spam"}}
"""

async def call_groq(messages):
    if not GROQ_API_KEY:
        return "No API key"

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.1-8b-instant", "messages": messages}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as r:
            data = await r.json()
            return data["choices"][0]["message"]["content"]

async def ask_ai(user_id, msg, admin=False):
    prompt = ADMIN_PROMPT if admin else MEMBER_PROMPT
    msgs = [{"role":"system","content":prompt},{"role":"user","content":msg}]
    return await call_groq(msgs)

# ============================================================
# ACTION EXECUTOR
# ============================================================
async def execute_action(guild, action_obj, channel):
    action = action_obj.get("action")
    data = action_obj.get("data", {})

    if action == "ban_member":
        member = guild.get_member(int(data["user_id"]))
        if member:
            await member.ban(reason=data.get("reason"))
            await channel.send(f"🔨 Banned {member}")

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

    # Roll system
    if message.guild and is_roll_channel(message.channel):
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

    # Quiz
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
async def ai(ctx, *, text):
    user_id = ctx.author.id
    now = utcnow()

    if user_id in user_last_called:
        if (now - user_last_called[user_id]).total_seconds() < COOLDOWN_SECONDS:
            return await ctx.send("Cooldown")

    user_last_called[user_id] = now

    admin = has_admin_role(ctx.author)
    reply = await ask_ai(user_id, text, admin)

    action = extract_json_action(reply)

    if action:
        return await execute_action(ctx.guild, action, ctx.channel)

    clean = clean_ai_reply(reply)
    if clean:
        await ctx.reply(clean)

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