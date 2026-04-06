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
NO_QUIZ_CHANNELS = {1481972997039587449}
ROLL_MIN         = 1
ROLL_MAX         = 350

# ============================================================
# INTENTS
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds  = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ============================================================
# STATE
# ============================================================
user_last_called     = {}
conversation_history = {}
user_points          = {}
quiz_active          = {}
vquiz_active         = {}
word_filter          = {}
auto_role_config     = {}
welcome_config       = {}
farewell_config      = {}
warn_records         = {}
roll_winning_number  = random.randint(ROLL_MIN, ROLL_MAX)
roll_lose_emojis     = ["😋", "😊", "😉", "😔", "😓", "🤫", "🥺", "😇"]
roll_win_emojis      = ["😍", "😎", "🥰", "😀", "🤩", "😛"]
roll_lose_index      = 0
roll_win_index       = 0

# ============================================================
# QUIZ BANK
# ============================================================
QUIZ_BANK = [
    # Science & Nature
    ("What is 7 x 8?", "56"),
    ("What planet is known as the Red Planet?", "mars"),
    ("What is the chemical symbol for water?", "h2o"),
    ("How many continents are there?", "7"),
    ("What is the fastest land animal?", "cheetah"),
    ("What is the square root of 144?", "12"),
    ("How many days are in a leap year?", "366"),
    ("What gas do plants absorb?", "carbon dioxide"),
    ("What is the hardest natural substance?", "diamond"),
    ("How many bones are in the human body?", "206"),
    ("What is the longest river in the world?", "nile"),
    ("How many players are on a football team?", "11"),
    ("What is the boiling point of water in Celsius?", "100"),
    ("What is the largest planet?", "jupiter"),
    ("What is the smallest country?", "vatican"),
    ("How many letters in the English alphabet?", "26"),
    ("What is the largest continent?", "asia"),
    ("How many colors are in a rainbow?", "7"),
    ("What is the largest desert?", "sahara"),
    ("How many teeth does an adult have?", "32"),
    ("How many strings does a guitar have?", "6"),
    ("What is the nearest star to Earth?", "sun"),
    ("What is the largest organ in the body?", "skin"),
    ("How many chambers does the heart have?", "4"),
    ("What is the chemical symbol for gold?", "au"),
    ("How many months have 31 days?", "7"),
    ("What is the largest mammal?", "blue whale"),
    ("How many sides does a triangle have?", "3"),
    ("What is the chemical symbol for iron?", "fe"),
    ("How many years in a decade?", "10"),
    ("What is the tallest animal?", "giraffe"),
    ("What gas do humans breathe?", "oxygen"),
    ("What is the largest bird?", "ostrich"),
    ("How many years in a century?", "100"),
    ("What is the smallest planet?", "mercury"),
    ("Most common gas in atmosphere?", "nitrogen"),
    ("What is the largest country by area?", "russia"),
    ("How many cards in a standard deck?", "52"),
    ("How many legs does a spider have?", "8"),
    ("What is the hottest planet?", "venus"),
    ("How many minutes in a day?", "1440"),
    ("How many keys on a piano?", "88"),
    ("How many bytes in a kilobyte?", "1024"),
    ("How many sides does a cube have?", "6"),
    ("How many players in volleyball?", "6"),
    ("What is the atomic number of carbon?", "6"),
    ("What is the square root of 256?", "16"),
    ("How many moons does Mars have?", "2"),
    ("What is the only planet that rotates on its side?", "uranus"),
    ("What is the only mammal that can truly fly?", "bat"),
    ("What is the longest bone in the body?", "femur"),
    ("How many hearts does an octopus have?", "3"),
    ("What is the most abundant metal in Earth's crust?", "aluminium"),
    ("How many zeros are in a trillion?", "12"),
    ("What is the only country with a non-rectangular flag?", "nepal"),
    ("What is the rarest blood type?", "ab negative"),
    ("How many zeros are in a googol?", "100"),
    ("What is the closest planet to the sun?", "mercury"),
    # History & People
    ("Who wrote Romeo and Juliet?", "shakespeare"),
    ("Who painted the Mona Lisa?", "da vinci"),
    ("What is the tallest mountain?", "everest"),
    ("How many planets in our solar system?", "8"),
    ("Who was the first US president?", "washington"),
    ("Who discovered gravity?", "newton"),
    ("What is the most spoken language?", "mandarin"),
    ("Who invented the light bulb?", "edison"),
    ("Who invented the telephone?", "bell"),
    ("What year did WW2 end?", "1945"),
    ("What year did WW1 start?", "1914"),
    ("How many players in basketball?", "5"),
    ("Who wrote Harry Potter?", "rowling"),
    ("How many hours in a week?", "168"),
    ("What country has the largest population?", "india"),
    ("Who invented the airplane?", "wright brothers"),
    ("Who invented the internet?", "tim berners-lee"),
    ("What was the first country to give women the right to vote?", "new zealand"),
    ("How old was Alexander the Great when he died?", "32"),
    ("What year was the Titanic built?", "1909"),
    ("Who was the first person to walk on the moon?", "neil armstrong"),
    # Brain Teasers & Fun
    ("What has hands but can't clap?", "clock"),
    ("What has keys but no locks?", "piano"),
    ("What comes once in a minute, twice in a moment, never in a thousand years?", "m"),
    ("What gets wetter the more it dries?", "towel"),
    ("What is 15% of 300?", "45"),
    ("How many sides does an octagon have?", "8"),
    ("What is the symbol for pi?", "3.14"),
    ("How many seconds are in a minute?", "60"),
    ("How many hours in a day?", "24"),
    ("How many days in a week?", "7"),
    ("How many cents in a dollar?", "100"),
    ("How many sides does a pentagon have?", "5"),
    ("How many degrees in a right angle?", "90"),
    ("What is the currency of Japan?", "yen"),
    ("What language is spoken in Brazil?", "portuguese"),
    ("What is the largest ocean on Earth?", "pacific"),
]

# ============================================================
# VISUAL QUIZ BANK  (question, image_url, accepted_answers)
# ============================================================
VISUAL_QUIZ_BANK = [
    # --- Famous Paintings ---
    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg/480px-Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg",
     ["mona lisa"]),

    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/640px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg",
     ["starry night", "the starry night"]),

    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f4/The_Scream.jpg/471px-The_Scream.jpg",
     ["the scream", "scream"]),

    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Sandro_Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project_-_edited.jpg/640px-Sandro_Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project_-_edited.jpg",
     ["birth of venus", "the birth of venus"]),

    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/%22The_Last_Supper%22_by_Leonardo_da_Vinci.jpg/640px-%22The_Last_Supper%22_by_Leonardo_da_Vinci.jpg",
     ["the last supper", "last supper"]),

    ("🎨 What is the name of this famous painting?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ed/Girl_with_a_Pearl_Earring.jpg/480px-Girl_with_a_Pearl_Earring.jpg",
     ["girl with a pearl earring"]),

    # --- Landmarks ---
    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/600px-Tour_Eiffel_Wikimedia_Commons.jpg",
     ["eiffel tower", "the eiffel tower"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Colosseo_2020.jpg/640px-Colosseo_2020.jpg",
     ["colosseum", "coliseum", "the colosseum"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Taj_Mahal_%28Edited%29.jpeg/640px-Taj_Mahal_%28Edited%29.jpeg",
     ["taj mahal"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Statue_of_Liberty_7.jpg/480px-Statue_of_Liberty_7.jpg",
     ["statue of liberty"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/The_Great_Wall_of_China_at_Jinshanling-edit.jpg/640px-The_Great_Wall_of_China_at_Jinshanling-edit.jpg",
     ["great wall", "great wall of china"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Burj_Khalifa_-_Jan_2006.jpg/400px-Burj_Khalifa_-_Jan_2006.jpg",
     ["burj khalifa"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Machu_Picchu%2C_Peru.jpg/640px-Machu_Picchu%2C_Peru.jpg",
     ["machu picchu"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/New_seven_wonders_Petra.jpg/640px-New_seven_wonders_Petra.jpg",
     ["petra"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Empire_State_Building_%28aerial_view%29.jpg/400px-Empire_State_Building_%28aerial_view%29.jpg",
     ["empire state building"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Kaabaiqbal1986.jpg/480px-Kaabaiqbal1986.jpg",
     ["kaaba", "mecca", "masjid al-haram"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Sydney_Opera_House_Sails.jpg/640px-Sydney_Opera_House_Sails.jpg",
     ["sydney opera house"]),

    ("🏛️ What famous landmark is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Clock_Tower_-_Palace_of_Westminster%2C_London_-_May_2007.jpg/400px-Clock_Tower_-_Palace_of_Westminster%2C_London_-_May_2007.jpg",
     ["big ben", "elizabeth tower"]),

    # --- Animals ---
    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Lion_waiting_in_Namibia.jpg/640px-Lion_waiting_in_Namibia.jpg",
     ["lion"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/African_Bush_Elephant.jpg/640px-African_Bush_Elephant.jpg",
     ["elephant", "african elephant"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Giraffe_Mikumi_National_Park.jpg/480px-Giraffe_Mikumi_National_Park.jpg",
     ["giraffe"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/640px-Grosser_Panda.JPG",
     ["panda", "giant panda"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/Felis_silvestris_silvestris_small_gradual_decrease.png/640px-Felis_silvestris_silvestris_small_gradual_decrease.png",
     ["cat", "wildcat"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/YellowLabradorLooking_new.jpg/640px-YellowLabradorLooking_new.jpg",
     ["dog", "labrador", "labrador retriever"]),

    ("🐾 What animal is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/South_African_Penguin_%28Spheniscus_demersus%29.jpg/640px-South_African_Penguin_%28Spheniscus_demersus%29.jpg",
     ["penguin"]),

    # --- Space & Science ---
    ("🚀 What planet is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Jupiter_New_Horizons.jpg/600px-Jupiter_New_Horizons.jpg",
     ["jupiter"]),

    ("🚀 What planet is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Saturn_during_Equinox.jpg/600px-Saturn_during_Equinox.jpg",
     ["saturn"]),

    ("🚀 What planet is this?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Mars_atmosphere.jpg/600px-Mars_atmosphere.jpg",
     ["mars"]),

    ("🔭 What is this famous space object?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Hs-2004-07-a-large_web.jpg/640px-Hs-2004-07-a-large_web.jpg",
     ["crab nebula", "nebula"]),

    ("🔭 What famous structure is shown here?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/HST-SM4.jpeg/600px-HST-SM4.jpeg",
     ["hubble", "hubble telescope", "hubble space telescope"]),

    # --- Famous People ---
    ("🧑 Who is this person?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Albert_Einstein_Head.jpg/480px-Albert_Einstein_Head.jpg",
     ["einstein", "albert einstein"]),

    ("🧑 Who is this person?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Lionel-Messi-Argentina-2022-FIFA-World-Cup_%28cropped%29.jpg/480px-Lionel-Messi-Argentina-2022-FIFA-World-Cup_%28cropped%29.jpg",
     ["messi", "lionel messi"]),

    ("🧑 Who is this person?",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Cristiano_Ronaldo_2019.jpg/480px-Cristiano_Ronaldo_2019.jpg",
     ["ronaldo", "cristiano ronaldo", "cr7"]),
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

GROQ_ADMIN_PROMPT = """You are an AI Discord Server Manager for admins only.
A live snapshot of the server is included at the top of every message — use it to answer questions about the server accurately.

You can perform these server management actions:
- create_channel: Create text/voice/category channels
- delete_channel: Delete a channel
- create_role: Create a new role with a color
- assign_role: Assign a role to a member
- remove_role: Remove a role from a member
- ban_member: Ban a member
- kick_member: Kick a member
- warn_member: Warn a member via DM
- setup_welcome: Set up welcome channel and message
- create_giveaway: Create a giveaway in a channel
- send_announcement: Send an announcement embed
- set_slowmode: Set slowmode in a channel

When the admin asks you to perform an action, ask ONE question at a time if info is missing.
Once you have ALL required info, output ONLY this JSON (no extra text):
```json
{"action": "action_name", "data": {"key": "value"}}
```

Required fields per action:
- create_channel: name, type (text/voice/category), topic (optional)
- delete_channel: channel_name
- create_role: name, color_hex (default #5865F2), hoist (true/false)
- assign_role: user_id, role_name
- remove_role: user_id, role_name
- ban_member: user_id, reason
- kick_member: user_id, reason
- warn_member: user_id, reason
- setup_welcome: channel_name, message (use {member} as placeholder)
- create_giveaway: channel_name, prize, duration_hours, winners
- send_announcement: channel_name, title, message, color_hex (default #5865F2)
- set_slowmode: channel_name, seconds

For plain questions or chat, just reply normally (no JSON).
Be short, friendly, and conversational."""

def get_server_snapshot(guild):
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count or 0
    text_channels = [c.name for c in guild.text_channels]
    voice_channels = [c.name for c in guild.voice_channels]
    roles = [r.name for r in guild.roles if r.name != "@everyone"]
    return (
        f"=== LIVE SERVER DATA ===\n"
        f"Server: {guild.name} | Boosts: {boost_count} (Level {boost_level}) | Members: {guild.member_count}\n"
        f"Text channels: {', '.join(text_channels) or 'none'}\n"
        f"Voice channels: {', '.join(voice_channels) or 'none'}\n"
        f"Roles: {', '.join(roles) or 'none'}\n"
        f"=== END SERVER DATA ==="
    )

def extract_json_action(text):
    # Walk the string finding balanced JSON objects that contain "action"
    for i, ch in enumerate(text):
        if ch != '{':
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[i:j + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and "action" in obj:
                            return obj
                    except Exception:
                        pass
                    break
    return None

def clean_ai_reply(text):
    cleaned = re.sub(r'```json.*?```', '', text, flags=re.DOTALL).strip()
    return cleaned if cleaned else None

async def execute_action(guild, action_obj, channel):
    action = action_obj.get("action")
    data   = action_obj.get("data", {})
    try:
        if action == "create_channel":
            ch_type = data.get("type", "text")
            if ch_type == "voice":
                await guild.create_voice_channel(data["name"])
            elif ch_type == "category":
                await guild.create_category(data["name"])
            else:
                await guild.create_text_channel(data["name"], topic=data.get("topic", ""))
            await channel.send(f"✅ Channel **#{data['name']}** created!")

        elif action == "delete_channel":
            ch = discord.utils.get(guild.channels, name=data["channel_name"])
            if ch:
                await ch.delete()
                await channel.send(f"🗑️ Channel **#{data['channel_name']}** deleted.")
            else:
                await channel.send(f"❌ Channel **#{data['channel_name']}** not found.")

        elif action == "create_role":
            color_str = data.get("color_hex", "5865F2").replace("#", "").replace("0x", "")
            color = discord.Color(int(color_str, 16))
            role = await guild.create_role(name=data["name"], color=color, hoist=data.get("hoist", False))
            await channel.send(f"✅ Role **@{role.name}** created!")

        elif action == "assign_role":
            member = guild.get_member(int(data["user_id"]))
            role   = discord.utils.get(guild.roles, name=data["role_name"])
            if member and role:
                await member.add_roles(role)
                await channel.send(f"✅ **@{role.name}** assigned to **{member.display_name}**.")
            else:
                await channel.send("❌ Member or role not found.")

        elif action == "remove_role":
            member = guild.get_member(int(data["user_id"]))
            role   = discord.utils.get(guild.roles, name=data["role_name"])
            if member and role:
                await member.remove_roles(role)
                await channel.send(f"✅ **@{role.name}** removed from **{member.display_name}**.")

        elif action == "ban_member":
            member = guild.get_member(int(data["user_id"]))
            if member:
                await member.ban(reason=data.get("reason", "No reason"))
                await channel.send(f"🔨 **{member.display_name}** banned. Reason: {data.get('reason', 'N/A')}")

        elif action == "kick_member":
            member = guild.get_member(int(data["user_id"]))
            if member:
                await member.kick(reason=data.get("reason", "No reason"))
                await channel.send(f"👢 **{member.display_name}** kicked.")

        elif action == "warn_member":
            member = guild.get_member(int(data["user_id"]))
            if member:
                embed = discord.Embed(
                    title="⚠️ Warning",
                    description=f"**Server:** {guild.name}\n**Reason:** {data.get('reason', 'No reason')}",
                    color=discord.Color.yellow()
                )
                try:
                    await member.send(embed=embed)
                except Exception:
                    pass
                await channel.send(f"⚠️ **{member.display_name}** has been warned.")

        elif action == "setup_welcome":
            ch = discord.utils.get(guild.text_channels, name=data["channel_name"])
            if not ch:
                ch = await guild.create_text_channel(data["channel_name"])
            embed = discord.Embed(
                title="👋 Welcome System Active!",
                description=f"Message template:\n> {data.get('message', '{member} welcome!')}",
                color=discord.Color.green()
            )
            await ch.send(embed=embed)
            await channel.send(f"✅ Welcome system set up in **#{ch.name}**!")

        elif action == "create_giveaway":
            ch_name = data.get("channel_name", "giveaway")
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if not ch:
                ch = await guild.create_text_channel(ch_name)
            from datetime import timedelta
            end_time = datetime.now(timezone.utc) + timedelta(hours=float(data.get("duration_hours", 24)))
            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {data.get('prize', 'Mystery Prize')}",
                description=(
                    f"**Winners:** {data.get('winners', 1)}\n"
                    f"**Ends:** <t:{int(end_time.timestamp())}:R>\n\n"
                    f"React with 🎉 to enter!"
                ),
                color=discord.Color.gold()
            )
            embed.set_footer(text="Ends at")
            gw_msg = await ch.send(embed=embed)
            await gw_msg.add_reaction("🎉")
            await channel.send(f"🎉 Giveaway live in **#{ch.name}**! → {gw_msg.jump_url}")

        elif action == "send_announcement":
            ch = discord.utils.get(guild.text_channels, name=data.get("channel_name", "announcements"))
            if not ch:
                ch = await guild.create_text_channel(data.get("channel_name", "announcements"))
            color_str = data.get("color_hex", "5865F2").replace("#", "").replace("0x", "")
            embed = discord.Embed(
                title=data.get("title", "📢 Announcement"),
                description=data.get("message", ""),
                color=discord.Color(int(color_str, 16))
            )
            await ch.send(embed=embed)
            await channel.send(f"📢 Announcement sent to **#{ch.name}**!")

        elif action == "set_slowmode":
            ch = discord.utils.get(guild.text_channels, name=data["channel_name"])
            if ch:
                await ch.edit(slowmode_delay=int(data.get("seconds", 0)))
                await channel.send(f"🐢 Slowmode set to **{data.get('seconds', 0)}s** in **#{ch.name}**.")

        else:
            await channel.send(f"⚠️ Unknown action: `{action}`")

    except discord.Forbidden:
        await channel.send("❌ I don't have permission to do that!")
    except Exception as e:
        await channel.send(f"❌ Error: `{e}`")

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

async def ask_groq_admin(user_id, message, guild):
    if not GROQ_API_KEY:
        return "⚠️ No GROQ_API_KEY set in Secrets!"
    snapshot = get_server_snapshot(guild)
    full_msg  = f"{snapshot}\n\nAdmin request: {message}"
    history   = conversation_history.get(user_id, [])
    messages  = [{"role": "system", "content": GROQ_ADMIN_PROMPT}]
    messages += history[-10:]
    messages.append({"role": "user", "content": full_msg})
    payload = {"model": "llama-3.1-8b-instant", "messages": messages, "max_tokens": 500, "temperature": 0.5}
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
        print(f"Groq admin error: {ex}")
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
    global roll_winning_number, roll_lose_index, roll_win_index
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
                won = random.random() < 0.01
                if won:
                    bot_roll = number
                else:
                    choices = [n for n in range(ROLL_MIN, ROLL_MAX + 1) if n != number]
                    bot_roll = random.choice(choices)

                if won:
                    emoji = roll_win_emojis[roll_win_index % len(roll_win_emojis)]
                    roll_win_index += 1
                    embed = discord.Embed(
                        title=f"{emoji} Congratulations!",
                        description=(
                            f"You have rolled the correct number.\n"
                            f"The number is **{number}**.\n\n"
                            "**Create a ticket to claim your Robux!**\n"
                            "Open a support ticket to receive your reward."
                        ),
                        color=discord.Color.gold()
                    )
                    embed.set_footer(text=f"Rolled by {message.author.display_name}")
                    await message.channel.send(embed=embed)
                else:
                    emoji = roll_lose_emojis[roll_lose_index % len(roll_lose_emojis)]
                    roll_lose_index += 1
                    embed = discord.Embed(
                        title=f"{emoji} Not this time!",
                        description=f"The number was **{bot_roll}**. Try again next time.",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text=f"Range: {ROLL_MIN}–{ROLL_MAX}")
                    await message.reply(embed=embed)
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

    # Visual Quiz answer — anyone can answer
    if ch_id in vquiz_active and not message.content.startswith(PREFIX):
        vq = vquiz_active[ch_id]
        guess = message.content.strip().lower()
        if any(guess == ans or ans in guess or guess in ans for ans in vq["answers"]):
            pts = user_points.get(message.author.id, 0) + 15
            user_points[message.author.id] = pts
            del vquiz_active[ch_id]
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"{message.author.mention} got it! The answer was **{vq['answers'][0].title()}**.\nYou earned **15 points**! Total: **{pts} pts** 🎉",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)
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
    if lower in ("commands", "cmds", "help", "cmd", "command"):
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
        if has_admin_role(ctx.author):
            reply      = await ask_groq_admin(user_id, user_input, ctx.guild)
            action_obj = extract_json_action(reply)
            if action_obj:
                await execute_action(ctx.guild, action_obj, ctx.channel)
            else:
                await ctx.reply(reply)
        else:
            reply = await ask_groq(user_id, user_input)
            await ctx.reply(reply)

# ============================================================
# HELP COMMAND
# ============================================================
@bot.command(name="help", aliases=["commands", "cmds", "cmd", "command"])
async def help_cmd(ctx):
    is_admin = has_admin_role(ctx.author)
    embed = discord.Embed(
        title="📋 Bot Commands",
        description="Here's everything you can do!\nUse `!ai [anything]` to chat with AI or trigger server actions (admins).",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="🤖 AI Chat",
        value="`!ai <message>` — Chat with AI or give it instructions\n`!a <message>` — Shortcut for `!ai`\n`!reset` — Clear your AI conversation history",
        inline=False
    )
    embed.add_field(
        name="🧠 Quiz & Points",
        value="`!quiz` — Text quiz (10 pts for correct answer)\n`!vquiz` — Visual image quiz (15 pts)\n`!points [@user]` — Check your/someone's points\n`!leaderboard` — Top 10 players",
        inline=False
    )
    embed.add_field(
        name="🎲 Roll for Robux",
        value=f"Type any number **{ROLL_MIN}–{ROLL_MAX}** in the roll channel!\nBot rolls too — match it to win **Robux**! (Very rare 🍀)",
        inline=False
    )
    embed.add_field(
        name="🔧 Utility",
        value="`!ping` — Bot latency",
        inline=False
    )
    if is_admin:
        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "`!mute @user [mins] [reason]` — Timeout a user\n"
                "`!unmute @user` — Remove timeout\n"
                "`!ban @user [reason]` — Ban a user\n"
                "`!unban <username>` — Unban a user\n"
                "`!kick @user [reason]` — Kick a user\n"
                "`!warn @user [reason]` — Warn a user\n"
                "`!warnings @user` — View warnings\n"
                "`!clear [amount]` — Delete messages"
            ),
            inline=False
        )
        embed.add_field(
            name="🏷️ Role Management",
            value=(
                "`!role create <name> [#color]`\n"
                "`!role delete <name>`\n"
                "`!role color <name> <#color>`\n"
                "`!role give @user <name>`\n"
                "`!role remove @user <name>`"
            ),
            inline=False
        )
        embed.add_field(
            name="🤖 AI Server Actions (say naturally)",
            value=(
                "`!ai ban/kick/mute/warn @user [reason]`\n"
                "`!ai create a text/voice channel called ...`\n"
                "`!ai create a role called ... in [color]`\n"
                "`!ai send announcement in #channel saying ...`\n"
                "`!ai set slowmode to X seconds in #channel`\n"
                "`!ai start a giveaway for [prize] in #channel`\n"
                "`!ai set up welcome messages in #channel`"
            ),
            inline=False
        )
    embed.set_footer(text="Powered by Groq AI (Llama 3.1) ⚡ | Admins see extra commands")
    await ctx.send(embed=embed)

# ============================================================
# MEMBER COMMANDS
# ============================================================
@bot.command(name="quiz")
async def quiz_cmd(ctx):
    ch_id = ctx.channel.id
    if ch_id in NO_QUIZ_CHANNELS:
        return await ctx.send("❌ Quiz commands are not allowed in this channel.")
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

@bot.command(name="vquiz")
async def vquiz_cmd(ctx):
    ch_id = ctx.channel.id
    if ch_id in NO_QUIZ_CHANNELS:
        return await ctx.send("❌ Quiz commands are not allowed in this channel.")
    if ch_id in vquiz_active:
        return await ctx.send("⚠️ A visual quiz is already active in this channel! Answer it first.")
    if ch_id in quiz_active:
        return await ctx.send("⚠️ A text quiz is already active! Finish that one first.")

    question, image_url, answers = random.choice(VISUAL_QUIZ_BANK)

    vquiz_active[ch_id] = {"question": question, "answers": answers, "image_url": image_url}

    embed = discord.Embed(
        title="🖼️ Visual Quiz!",
        description=f"**{question}**\n\n🕐 You have **45 seconds** — anyone can answer!\n_Type your answer in the chat._",
        color=discord.Color.blurple()
    )
    embed.set_image(url=image_url)
    embed.set_footer(text="15 points for correct answer! 🏆")
    await ctx.send(embed=embed)

    await asyncio.sleep(45)
    if ch_id in vquiz_active and vquiz_active[ch_id]["image_url"] == image_url:
        correct = vquiz_active[ch_id]["answers"][0].title()
        del vquiz_active[ch_id]
        await ctx.send(f"⏰ Time's up! Nobody got it. The answer was **{correct}**.")

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
    try:
        dm_embed = discord.Embed(
            title="🔇 You have been muted",
            description=f"**Server:** {ctx.guild.name}\n**Duration:** {minutes} minutes\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        await member.send(embed=dm_embed)
    except Exception:
        pass
    await ctx.send(f"🔇 {member.mention} has been muted for **{minutes} min**. Reason: {reason}")

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
    try:
        dm_embed = discord.Embed(
            title="🔨 You have been banned",
            description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        await member.send(embed=dm_embed)
    except Exception:
        pass
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} has been banned. Reason: {reason}")

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
    try:
        dm_embed = discord.Embed(
            title="👢 You have been kicked",
            description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        await member.send(embed=dm_embed)
    except Exception:
        pass
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} has been kicked. Reason: {reason}")

@bot.command(name="warn")
async def warn_cmd(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not has_admin_role(ctx.author):
        return await ctx.send("❌ You need **Owner** or **Management** role.")
    warn_records.setdefault(ctx.guild.id, {}).setdefault(str(member.id), []).append(reason)
    count = len(warn_records[ctx.guild.id][str(member.id)])
    dm_embed = discord.Embed(
        title="⚠️ You have been warned",
        description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}\n**Total warnings:** {count}",
        color=discord.Color.yellow()
    )
    try:
        await member.send(embed=dm_embed)
    except Exception:
        pass
    await ctx.send(f"⚠️ {member.mention} has been warned ({count} total). Reason: {reason}")

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


# ============================================================
# RUN
# ============================================================
import os
bot.run(os.getenv('DISCORD_TOKEN'))