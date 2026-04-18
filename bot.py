import discord
from discord.ext import commands
import asyncio
import json
import re
import os
from datetime import datetime, timezone
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
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

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!", "/"), intents=intents, help_command=None)

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

# ================= GAME STATE =================
game_sessions = {}

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
# GAME LOGIC
# ============================================================

def new_game(user_id):
    game_sessions[user_id] = {
        "player_hp": 100,
        "enemy_hp": 100
    }

def game_status(user_id):
    g = game_sessions[user_id]
    return f"YOU: {g['player_hp']} ❤️ | ENEMY: {g['enemy_hp']} ❤️"

def game_move(user_id, action):
    g = game_sessions[user_id]

    if action == "shoot":
        dmg = random.randint(10, 25)
        g["enemy_hp"] -= dmg

    elif action in ["up", "down", "left", "right"]:
        if random.random() < 0.3:
            return "🛡️ You dodged!"

    if g["enemy_hp"] > 0:
        g["player_hp"] -= random.randint(5, 15)

    if g["player_hp"] <= 0:
        return "💀 You lost!"
    if g["enemy_hp"] <= 0:
        return "🎉 You won!"

    return game_status(user_id)

# ============================================================
# BUTTON UI
# ============================================================

class GameView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        return interaction.user.id == self.user_id

    async def update(self, interaction, action):
        msg = game_move(self.user_id, action)
        await interaction.response.edit_message(
            content=f"🎮 **Pixel Battle Arena**\n{msg}",
            view=self
        )

    @discord.ui.button(label="⬆️", style=discord.ButtonStyle.secondary, row=0)
    async def up(self, interaction, button):
        await self.update(interaction, "up")

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def left(self, interaction, button):
        await self.update(interaction, "left")

    @discord.ui.button(label="💥 Shoot", style=discord.ButtonStyle.danger, row=1)
    async def shoot(self, interaction, button):
        await self.update(interaction, "shoot")

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def right(self, interaction, button):
        await self.update(interaction, "right")

    @discord.ui.button(label="⬇️", style=discord.ButtonStyle.secondary, row=2)
    async def down(self, interaction, button):
        await self.update(interaction, "down")

    @discord.ui.button(label="🔄 Restart", style=discord.ButtonStyle.success, row=3)
    async def restart(self, interaction, button):
        new_game(self.user_id)
        await interaction.response.edit_message(
            content="🎮 **Pixel Battle Arena**\nGame restarted!",
            view=self
        )

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
async def battle(ctx):
    new_game(ctx.author.id)
    view = GameView(ctx.author.id)
    await ctx.send("🎮 **Pixel Battle Arena**\n" + game_status(ctx.author.id), view=view)

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