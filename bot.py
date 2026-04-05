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
DISCORD_TOKEN    = os.environ.get("DISCORD_TOKEN", "")
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
PREFIX           = "!"
COOLDOWN_SECONDS = 5
ADMIN_ROLES      = ["Owner", "Management"]
ROLL_CHANNEL     = "roll-for-robux"
ROLL_CHANNEL_ID  = 1490276530452955246
ROLL_MIN         = 1
ROLL_MAX         = 350

# ============================================================
# INTENTS
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds  = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ============================================================
# STATE
# ============================================================
user_last_called     = {}
conversation_history = {}
user_points          = {}
quiz_active          = {}
word_filter          = {}
auto_role_config     = {}
welcome_config       = {}
farewell_config      = {}
warn_records         = {}
roll_winning_number  = random.randint(ROLL_MIN, ROLL_MAX)

# ============================================================
# QUIZ BANK
# ============================================================
QUIZ_BANK = [
    ("What is the capital of France?", "paris"),
    ("What is 7 x 8?", "56"),
    ("What planet is known as the Red Planet?", "mars"),
    ("How many sides does a hexagon have?", "6"),
    ("What is the largest ocean on Earth?", "pacific"),
    ("Who wrote Romeo and Juliet?", "shakespeare"),
    ("What is the chemical symbol for water?", "h2o"),
    ("How many continents are there?", "7"),
    ("What is the fastest land animal?", "cheetah"),
    ("What is the square root of 144?", "12"),
    ("What country has the largest population?", "india"),
    ("How many days are in a leap year?", "366"),
    ("What gas do plants absorb?", "carbon dioxide"),
    ("What is the hardest natural substance?", "diamond"),
    ("How many bones are in the human body?", "206"),
    ("What is the longest river in the world?", "nile"),
    ("What is the capital of Japan?", "tokyo"),
    ("How many players are on a football team?", "11"),
    ("What is the boiling point of water in Celsius?", "100"),
    ("What is the capital of Germany?", "berlin"),
    ("How many seconds are in a minute?", "60"),
    ("What is the largest planet?", "jupiter"),
    ("Who invented the telephone?", "bell"),
    ("What is the smallest country?", "vatican"),
    ("How many letters in the English alphabet?", "26"),
    ("What is the currency of Japan?", "yen"),
    ("What is the capital of Australia?", "canberra"),
    ("How many hours in a day?", "24"),
    ("What language is spoken in Brazil?", "portuguese"),
    ("What is the capital of Canada?", "ottawa"),
    ("Who painted the Mona Lisa?", "da vinci"),
    ("What is the tallest mountain?", "everest"),
    ("How many planets in our solar system?", "8"),
    ("What is the capital of Italy?", "rome"),
    ("What is the largest continent?", "asia"),
    ("How many colors are in a rainbow?", "7"),
    ("What is the capital of Spain?", "madrid"),
    ("Who was the first US president?", "washington"),
    ("What is the capital of China?", "beijing"),
    ("What is the largest desert?", "sahara"),
    ("How many teeth does an adult have?", "32"),
    ("What is the capital of Russia?", "moscow"),
    ("What animal is the king of the jungle?", "lion"),
    ("How many strings does a guitar have?", "6"),
    ("What is the capital of Brazil?", "brasilia"),
    ("What is the nearest star to Earth?", "sun"),
    ("What is the capital of India?", "new delhi"),
    ("How many wheels does a tricycle have?", "3"),
    ("What is the largest organ in the body?", "skin"),
    ("What is the capital of Mexico?", "mexico city"),
    ("Who discovered gravity?", "newton"),
    ("How many days in a week?", "7"),
    ("What is the capital of South Korea?", "seoul"),
    ("What is the most spoken language?", "mandarin"),
    ("How many chambers does the heart have?", "4"),
    ("What is the capital of Egypt?", "cairo"),
    ("What is the chemical symbol for gold?", "au"),
    ("How many months have 31 days?", "7"),
    ("What is the capital of Turkey?", "ankara"),
    ("Who invented the light bulb?", "edison"),
    ("What is the capital of Argentina?", "buenos aires"),
    ("What is the largest mammal?", "blue whale"),
    ("How many sides does a triangle have?", "3"),
    ("What is the chemical symbol for iron?", "fe"),
    ("How many years in a decade?", "10"),
    ("What is the tallest animal?", "giraffe"),
    ("How many cents in a dollar?", "100"),
    ("What gas do humans breathe?", "oxygen"),
    ("How many sides does a pentagon have?", "5"),
    ("What is the largest bird?", "ostrich"),
    ("How many years in a century?", "100"),
    ("Who wrote Harry Potter?", "rowling"),
    ("How many hours in a week?", "168"),
    ("What is the smallest planet?", "mercury"),
    ("How many degrees in a right angle?", "90"),
    ("What is the capital of Bangladesh?", "dhaka"),
    ("Most common gas in atmosphere?", "nitrogen"),
    ("How many sides does an octagon have?", "8"),
    ("What is the largest country by area?", "russia"),
    ("How many cards in a standard deck?", "52"),
    ("What is the symbol for pi?", "3.14"),
    ("How many legs does a spider have?", "8"),
    ("What is the hottest planet?", "venus"),
    ("How many minutes in a day?", "1440"),
    ("What year did WW2 end?", "1945"),
    ("How many players in basketball?", "5"),
    ("What is the capital of Greece?", "athens"),
    ("How many keys on a piano?", "88"),
    ("What is the capital of Portugal?", "lisbon"),
    ("How many bytes in a kilobyte?", "1024"),
    ("What is the capital of Netherlands?", "amsterdam"),
    ("How many sides does a cube have?", "6"),
    ("What is the capital of Sweden?", "stockholm"),
    ("How many players in volleyball?", "6"),
    ("What is the capital of Denmark?", "copenhagen"),
    ("What is the capital of Norway?", "oslo"),
    ("What is the atomic number of carbon?", "6"),
    ("What is the capital of Pakistan?", "islamabad"),
    ("What is the capital of Philippines?", "manila"),
    ("What year did WW1 start?", "1914"),
]

# ============================================================
# HELPERS
# ============================================================
def has_admin_role(member):
    return member.guild.owner_id == member.id or any(r.name in ADMIN_ROLES for r in member.roles)

def is_roll_channel(channel):
    return channel.id == ROLL_CHANNEL_ID or ROLL_CHANNEL in channel.name.lower()

# ============================================================
# GROQ AI
# ============================================================
GROQ_SYSTEM_PROMPT = """You are a friendly Discord bot assistant. Chat about ANYTHING — answer questions, tell jokes, give opinions, help with homework, discuss games, etc.
Be short (1-3 sentences), casual, friendly, with occasional emojis. You are a chat companion."""

async def ask_groq(user_id, message):
    if not GROQ_API_KEY:
        return "⚠️ No GROQ_API_KEY set in Secrets!"
    history  = conversation_history.get(user_id, [])
    messages = [{"role": "system", "content": GROQ_SYSTEM_PROMPT}]
    messages += history[-10:]
    messages.append({"role": "user", "content": message})
    payload = {"model": "llama-3.1-8b-instant", "messages": messages, "max_tokens": 300, "temperature": 0.7}
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status == 429:
                    return "⏳ Rate-limited — try again in a moment!"
                if resp.status in (401, 403):
                    return "❌ Invalid GROQ_API_KEY."
                if resp.status != 200:
                    return f"❌ Groq error ({resp.status}). Try again."
                result = await resp.json()
                reply  = result["choices"][0]["message"]["content"].strip()
        h = conversation_history.setdefault(user_id, [])
        h.append({"role": "user", "content": message})
        h.append({"role": "assistant", "content": reply})
        conversation_history[user_id] = h[-20:]
        return reply
    except asyncio.TimeoutError:
        return "⏳ AI is taking too long — try again!"
    except Exception as ex:
        print(f"Groq error: {ex}")
        return "❌ Couldn't reach AI right now."

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online! Roll winning number: {roll_winning_number}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your server 👁️"))

@bot.event
async def on_member_join(member):
    guild = member.guild
    role_name = auto_role_config.get(guild.id)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            try:
                await member.add_roles(role)
            except Exception:
                pass
    cfg = welcome_config.get(guild.id)
    ch_name = cfg["channel_name"] if cfg else "welcome"
    ch = discord.utils.get(guild.text_channels, name=ch_name)
    if ch:
        msg = (cfg["message"] if cfg else "Welcome {member} to {server}!").replace("{member}", member.mention).replace("{server}", guild.name)
        embed = discord.Embed(description=msg, color=discord.Color.green(), timestamp=utcnow())
        embed.set_author(name=f"Welcome to {guild.name}!", icon_url=member.display_avatar.url)
        await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    cfg = farewell_config.get(member.guild.id)
    if cfg:
        ch = discord.utils.get(member.guild.text_channels, name=cfg["channel_name"])
        if ch:
            msg = cfg["message"].replace("{member}", member.display_name).replace("{server}", member.guild.name)
            embed = discord.Embed(description=msg, color=discord.Color.red(), timestamp=utcnow())
            embed.set_author(name="Member left", icon_url=member.display_avatar.url)
            await ch.send(embed=embed)

@bot.event
async def on_message(message):
    global roll_winning_number
    if message.author.bot:
        return

    # Word filter
    if message.guild and message.guild.id in word_filter:
        if any(w in message.content.lower() for w in word_filter[message.guild.id]):
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} Message removed — filtered word.", delete_after=5)
            except Exception:
                pass
            return

    # Roll for Robux
    if message.guild and is_roll_channel(message.channel):
        content = message.content.strip()
        if re.match(r"^\d+$", content):
            number = int(content)
            if ROLL_MIN <= number <= ROLL_MAX:
                if random.random() < 0.05:
                    embed = discord.Embed(
                        title="🎉 WINNER!",
                        description=(
                            f"{message.author.mention} guessed the correct number — **{number}**!\n\n"
                            "**Create a ticket to claim your Robux!**\n"
                            "Go to the ticket channel and open a support ticket to receive your reward."
                        ),
                        color=discord.Color.gold()
                    )
                    embed.set_footer(text="Congratulations! 🏆")
                    await message.channel.send(embed=embed)
                else:
                    await message.reply(
                        f"❌ **{number}** isn't the correct number. Keep trying! ({ROLL_MIN}–{ROLL_MAX})"
                    )
                return

    # Quiz answer
    ch_id = message.channel.id
    if ch_id in quiz_active and not message.content.startswith(PREFIX):
        q = quiz_active[ch_id]
        if message.author.id == q["user_id"]:
            answer = message.content.strip().lower()
            correct = q["answer"].lower()
            if answer == correct or correct in answer:
                pts = user_points.get(message.author.id, 0) + 10
                user_points[message.author.id] = pts
                del quiz_active[ch_id]
                await message.reply(f"✅ Correct! You earned **10 points**. Total: **{pts} pts** 🎉")
            else:
                del quiz_active[ch_id]
                await message.reply(f"❌ Wrong! The correct answer was **{q['answer']}**.")
            return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Couldn't find that member or role.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error: {error}")

# ============================================================
# !ai — main command (members + admins)
# ============================================================
@bot.command(name="ai", aliases=["a"])
async def ai_cmd(ctx, *, user_input: str):
    lower = user_input.lower().strip()

    # !ai commands — shows full embed, but admin section only visible to admins
    if lower in ("commands", "cmds", "help"):
        embed = discord.Embed(
            title="🤖 AI Server Manager",
            description="Just tell me what you want in plain English using `!ai`.\nNo commands to memorise — the AI understands you.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="🤖 AI Chat", value="`!ai [anything]` — Ask me anything!", inline=False)
        embed.add_field(name="🧠 Quiz & Points", value="`!quiz` — Start a quiz (10 pts per correct answer)\n`!points` — Check your points\n`!leaderboard` — Top 10 players", inline=False)
        embed.add_field(name="🎲 Roll for Robux", value=f"Type a number between **{ROLL_MIN}–{ROLL_MAX}** in the roll channel!\nGuess the winning number and win **300 Robux**!", inline=False)
        embed.add_field(name="🔧 Utility", value="`!reset` — Clear your AI chat history\n`!ping` — Bot latency", inline=False)

        if has_admin_role(ctx.author):
            embed.add_field(name="🛡️ Moderation (Admin only)", value=(
                "`!mute @user [minutes] [reason]`\n"
                "`!unmute @user`\n"
                "`!ban @user [reason]`\n"
                "`!unban [username]`\n"
                "`!kick @user [reason]`\n"
                "`!warn @user [reason]`\n"
                "`!warnings @user`\n"
                "`!clear [amount]`"
            ), inline=False)
            embed.add_field(name="🏷️ Roles (Admin only)", value=(
                "`!role create [name] [#color]`\n"
                "`!role delete [name]`\n"
                "`!role color [name] [#color]`\n"
                "`!role give @user [name]`\n"
                "`!role remove @user [name]`"
            ), inline=False)
            embed.add_field(name="🎲 Roll Admin", value="`!newroll` — Reset winning number", inline=False)
            embed.add_field(name="🤖 AI Actions (Admin only)", value=(
                "`!ai ban @user for spamming`\n"
                "`!ai kick @user`\n"
                "`!ai warn @user for being rude`\n"
                "`!ai mute @user for 10 minutes`\n"
                "`!ai create text channel called general`\n"
                "`!ai create voice channel called Music`\n"
                "`!ai create role called VIP in gold`\n"
                "`!ai send announcement in #news saying Hello!`\n"
                "`!ai set slowmode to 10 seconds in #general`\n"
                "`!ai start a giveaway for Nitro 24 hours`\n"
                "`!ai filter the words: bad, word2`\n"
                "`!ai set up welcome messages in #welcome`"
            ), inline=False)

        embed.set_footer(text="Powered by Groq AI (Llama 3.1) ⚡")
        return await ctx.send(embed=embed)

    # Cooldown
    user_id = ctx.author.id
    now     = utcnow()
    last    = user_last_called.get(user_id)
    if last and (now - last).total_seconds() < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last).total_seconds())
        return await ctx.send(f"⏳ Wait **{remaining}s** before using `!ai` again.")
    user_last_called[user_id] = now

    async with ctx.typing():
        reply = await ask_groq(user_id, user_input)
        await ctx.reply(reply)

# ============================================================
# MEMBER COMMANDS
# ============================================================
@bot.command(name="quiz")
async def quiz_cmd(ctx):
    ch_id = ctx.channel.id
    if ch_id in quiz_active:
        return await ctx.send("⚠️ A quiz is already active! Answer it first.")
    q, a = random.choice(QUIZ_BANK)
    quiz_active[ch_id] = {"question": q, "answer": a, "user_id": ctx.author.id}
    embed = discord.Embed(title="🧠 Quiz Time!", description=f"**{q}**\n\nType your answer! You have **30 seconds**.", color=discord.Color.blurple())
    embed.set_footer(text="10 points for correct answer!")
    await ctx.send(embed=embed)
    await asyncio.sleep(30)
    if ch_id in quiz_active and quiz_active[ch_id]["question"] == q:
        del quiz_active[ch_id]
        await ctx.send(f"⏰ Time's up! The answer was **{a}**.")

@bot.command(name="points")
async def points_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    pts = user_points.get(target.id, 0)
    await ctx.send(f"🏆 **{target.display_name}** has **{pts} points**.")

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard_cmd(ctx):
    if not user_points:
        return await ctx.send("No points recorded yet!")
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
    desc = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, pts) in enumerate(sorted_users):
        m = ctx.guild.get_member(uid)
        name = m.display_name if m else f"User {uid}"
        medal = medals[i] if i < 3 else f"**#{i+1}**"
        desc += f"{medal} {name} — **{pts} pts**\n"
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping_cmd(ctx):
    await ctx.send(f"🏓 Pong! **{round(bot.latency * 1000)}ms**")

@bot.command(name="reset")
async def reset_cmd(ctx):
    conversation_history.pop(ctx.author.id, None)
    await ctx.send("🔄 Chat history cleared!")

# ============================================================
# ADMIN COMMANDS
# ============================================================
@bot.command(name="mute")
async def mute_cmd(ctx, member: discord.Member, minutes: int = 10, *, reason: str = "No reason"):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    await ctx.send(f"🔇 **{member.display_name}** muted for **{minutes} min**. Reason: {reason}")

@bot.command(name="unmute")
async def unmute_cmd(ctx, member: discord.Member):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    await member.timeout(None)
    await ctx.send(f"🔊 **{member.display_name}** unmuted.")

@bot.command(name="ban")
async def ban_cmd(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    await member.ban(reason=reason)
    await ctx.send(f"🔨 **{member.display_name}** banned. Reason: {reason}")

@bot.command(name="unban")
async def unban_cmd(ctx, *, username: str):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    banned = [entry async for entry in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user) == username or entry.user.name == username:
            await ctx.guild.unban(entry.user)
            return await ctx.send(f"✅ **{entry.user}** unbanned.")
    await ctx.send(f"❌ No banned user found: **{username}**.")

@bot.command(name="kick")
async def kick_cmd(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member.display_name}** kicked. Reason: {reason}")

@bot.command(name="warn")
async def warn_cmd(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    warn_records.setdefault(ctx.guild.id, {}).setdefault(str(member.id), []).append(reason)
    count = len(warn_records[ctx.guild.id][str(member.id)])
    embed = discord.Embed(title="⚠️ Warning", description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}\n**Total warnings:** {count}", color=discord.Color.yellow())
    try:
        await member.send(embed=embed)
    except Exception:
        pass
    await ctx.send(f"⚠️ **{member.display_name}** warned ({count} total). Reason: {reason}")

@bot.command(name="warnings")
async def warnings_cmd(ctx, member: discord.Member):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    warns = warn_records.get(ctx.guild.id, {}).get(str(member.id), [])
    if not warns:
        return await ctx.send(f"✅ **{member.display_name}** has no warnings.")
    desc = "\n".join([f"{i+1}. {w}" for i, w in enumerate(warns)])
    embed = discord.Embed(title=f"⚠️ Warnings for {member.display_name}", description=desc, color=discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command(name="clear")
async def clear_cmd(ctx, amount: int = 10):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Cleared **{amount}** messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="role")
async def role_cmd(ctx, action: str, *, args: str = ""):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    action = action.lower()

    if action == "create":
        parts = args.split()
        color_hex = "5865F2"
        name = args
        for part in parts:
            clean = part.replace("#", "")
            if len(clean) == 6 and all(c in "0123456789abcdefABCDEF" for c in clean):
                color_hex = clean
                name = args.replace(part, "").strip()
                break
        role = await ctx.guild.create_role(name=name, color=discord.Color(int(color_hex, 16)))
        await ctx.send(f"✅ Role **@{role.name}** created!")

    elif action == "delete":
        role = discord.utils.get(ctx.guild.roles, name=args.strip())
        if not role:
            return await ctx.send(f"❌ Role **{args}** not found.")
        await role.delete()
        await ctx.send(f"🗑️ Role **@{args}** deleted.")

    elif action == "color":
        parts = args.split()
        if len(parts) < 2:
            return await ctx.send("Usage: `!role color [role name] [#color]`")
        color_hex = parts[-1].replace("#", "")
        role_name = " ".join(parts[:-1])
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            return await ctx.send(f"❌ Role **{role_name}** not found.")
        await role.edit(color=discord.Color(int(color_hex, 16)))
        await ctx.send(f"🎨 Role **@{role.name}** color updated!")

    elif action == "give":
        if not ctx.message.mentions:
            return await ctx.send("Usage: `!role give @user RoleName`")
        member = ctx.message.mentions[0]
        role_name = re.sub(r"<@!?\d+>", "", args).strip()
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            return await ctx.send(f"❌ Role **{role_name}** not found.")
        await member.add_roles(role)
        await ctx.send(f"✅ **@{role.name}** given to **{member.display_name}**.")

    elif action == "remove":
        if not ctx.message.mentions:
            return await ctx.send("Usage: `!role remove @user RoleName`")
        member = ctx.message.mentions[0]
        role_name = re.sub(r"<@!?\d+>", "", args).strip()
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            return await ctx.send(f"❌ Role **{role_name}** not found.")
        await member.remove_roles(role)
        await ctx.send(f"✅ **@{role.name}** removed from **{member.display_name}**.")

    else:
        await ctx.send("❌ Usage: `!role create/delete/color/give/remove`")

@bot.command(name="newroll")
async def newroll_cmd(ctx):
    global roll_winning_number
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    roll_winning_number = random.randint(ROLL_MIN, ROLL_MAX)
    await ctx.send(f"🎲 New winning number set! Let the guessing begin ({ROLL_MIN}–{ROLL_MAX}).")
    print(f"New winning number: {roll_winning_number}")

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)