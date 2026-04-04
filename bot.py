import discord
from discord.ext import commands
import asyncio
import json
import re
import os
import random
from datetime import datetime, timedelta, timezone

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ============================================================
# CONFIG
# ============================================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PREFIX = "!"
COOLDOWN_SECONDS = 5

# ============================================================
# INTENTS
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ============================================================
# STATE
# ============================================================
user_last_called = {}
conversation_history = {}  # user_id -> list of {role, content} messages

# ============================================================
# BUILT-IN AI RESPONSES
# ============================================================
RESPONSES = {
    "greeting": [
        "Hello! How can I help you manage your server? 😊",
        "Hey there! What can I do for you today?",
        "Hi! Ready to help. What do you need?",
        "Hello! What's up? Type `!commands` to see what I can do.",
    ],
    "farewell": [
        "See you around! 👋",
        "Goodbye! I'll be here when you need me.",
        "Later! Feel free to ask anytime.",
    ],
    "how_are_you": [
        "Running great — no API limits to worry about! 😄 What can I do for you?",
        "All systems go! Ready to help manage your server.",
        "Doing well! What do you need?",
    ],
    "thanks": [
        "You're welcome! Anything else I can help with?",
        "Happy to help! 😊",
        "Anytime! Let me know if you need anything else.",
        "No problem at all!",
    ],
    "compliment": [
        "Aw, thank you! You're pretty great yourself 😊",
        "That's so kind! Just doing my job 🤖",
        "Thanks! I try my best to be helpful!",
    ],
    "joke": [
        "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
        "I told a joke about Discord once. It had terrible latency. 😄",
        "Why was the bot banned? It kept spamming 'Hello World'! 🤖",
        "What do you call a Discord bot that tells bad jokes? Me, apparently. 😅",
        "Why did the moderator cross the road? To ban someone on the other side! 🔨",
    ],
    "unknown": [
        "I'm not sure I understood that. Try `!commands` to see what I can do!",
        "Hmm, didn't catch that. Use `!commands` for a list of things I can help with.",
        "Not sure what you mean. Try things like `!ai create channel called general` or `!ai how many members`.",
    ],
}

# ============================================================
# GROQ AI — real language model, free tier (14,400 req/day)
# Get your free key at: https://console.groq.com
# ============================================================
import urllib.request
import urllib.error

GROQ_SYSTEM_PROMPT = (
    "You are a friendly, witty Discord bot assistant. "
    "You can chat about anything — topics, questions, opinions, stories, jokes, advice, whatever the user says. "
    "Keep replies short and conversational (1-3 sentences max). "
    "Use casual, friendly language. Occasionally use emojis where natural. "
    "If someone asks you to do something in their Discord server (create channel, ban user, etc.), "
    "tell them to use the `!ai` command with server action keywords, for example: `!ai create channel called general`."
)

async def ask_groq(user_id, message):
    if not GROQ_API_KEY:
        return "⚠️ No GROQ_API_KEY set. Add it in Secrets to enable AI chat!"

    # Build conversation history for context (last 10 messages)
    history = conversation_history.get(user_id, [])
    messages = [{"role": "system", "content": GROQ_SYSTEM_PROMPT}]
    messages += history[-10:]
    messages.append({"role": "user", "content": message})

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "max_tokens": 200,
        "temperature": 0.8,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            reply = result["choices"][0]["message"]["content"].strip()
            # Save to history
            if user_id not in conversation_history:
                conversation_history[user_id] = []
            conversation_history[user_id].append({"role": "user", "content": message})
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            # Trim history to last 20 messages
            conversation_history[user_id] = conversation_history[user_id][-20:]
            return reply
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"Groq error {e.code}: {body}")
        if e.code == 429:
            return "⏳ I'm being rate-limited right now. Try again in a moment!"
        if e.code in (401, 403):
            return "❌ Invalid GROQ_API_KEY. Please check your Secrets."
        return f"❌ AI error ({e.code}). Try again later."
    except Exception as e:
        print(f"Groq error: {e}")
        return "❌ Couldn't reach the AI right now. Try again in a moment!"

# ============================================================
# TOPIC KEYWORD MAP  (kept for instant server-info replies)
# ============================================================
TOPIC_RESPONSES = {
    ("cat", "cats", "kitten", "kitty"): [
        "Cats are awesome! 🐱 Do you have one?",
        "Meow! 🐱 Cats are so independent and cool.",
        "I'm a bot, but if I had a pet it'd definitely be a cat! 😄",
    ],
    ("dog", "dogs", "puppy", "pup"): [
        "Dogs are the best! 🐶 So loyal and friendly.",
        "Man's best friend! 🐕 Do you have a dog?",
        "Aww, dogs are amazing! What breed are you thinking of?",
    ],
    ("food", "eat", "eating", "hungry", "pizza", "burger", "sushi", "chicken"): [
        "Ooh, food talk! 🍕 What's your favourite thing to eat?",
        "Now I wish I could eat! 🤖 What are you having?",
        "Sounds delicious! Food is one of the best things in life. 😄",
    ],
    ("game", "gaming", "games", "minecraft", "fortnite", "roblox", "valorant", "cod"): [
        "Gaming! 🎮 What are you playing lately?",
        "Nice! Gaming is great. What's your favourite game?",
        "A fellow gamer! 🎮 PC, console, or mobile?",
    ],
    ("music", "song", "songs", "listen", "spotify", "playlist"): [
        "Music is life! 🎵 What are you listening to?",
        "Nice taste! 🎶 What genre do you like?",
        "I'd love to have ears to hear music! 🤖🎵 What's your favourite artist?",
    ],
    ("movie", "movies", "film", "films", "watch", "netflix", "cinema"): [
        "Movies are great! 🎬 What are you watching?",
        "Good pick! 🎥 What genre do you prefer?",
        "Love the cinema! 🍿 What's your all-time favourite movie?",
    ],
    ("school", "study", "studying", "homework", "exam", "test", "college", "university"): [
        "School life! 📚 How's studying going?",
        "Hang in there! 💪 Study hard and it'll pay off.",
        "Learning is valuable! 📖 What subject are you studying?",
    ],
    ("sport", "sports", "football", "soccer", "basketball", "cricket", "tennis"): [
        "Sports fan! ⚽ What's your favourite sport?",
        "Nice! 🏆 Do you play or just watch?",
        "Sports are amazing! 🏅 What team do you support?",
    ],
    ("work", "job", "working", "boss", "office", "career"): [
        "Work life! 💼 How's it going?",
        "The grind! 💪 Hope work is treating you well.",
        "Working hard I see! 🧑‍💻 Take breaks too — it's important!",
    ],
    ("sleep", "tired", "sleepy", "nap", "insomnia", "bed"): [
        "Get some rest! 😴 Sleep is super important.",
        "Tired huh? 😪 Hope you get a good sleep soon!",
        "Same... if only bots could sleep! 🤖💤",
    ],
    ("money", "rich", "broke", "cash", "earn", "income"): [
        "Money talk! 💸 Saving up for something?",
        "The hustle is real! 💰 Hope things pick up for you.",
        "Money makes the world go round, as they say! 💵",
    ],
    ("bored", "boring", "nothing to do"): [
        "Bored? Try `!ai tell me a joke` 😄",
        "Boredom is a sign you need a new hobby! 🎮🎨🎵 What do you usually enjoy?",
        "I'm here to chat! Ask me anything 😊",
    ],
    ("love", "crush", "relationship", "dating", "girlfriend", "boyfriend"): [
        "Ooh, relationship talk! ❤️ That's sweet.",
        "Love is a beautiful thing! ❤️",
        "Aww! Hope it's going well 😊",
    ],
    ("happy", "excited", "great", "amazing", "wonderful", "awesome"): [
        "That's great to hear! 😄 Keep that energy!",
        "Love the positivity! 🙌",
        "Awesome! Good vibes only 🎉",
    ],
    ("sad", "upset", "depressed", "unhappy", "lonely", "cry", "crying"): [
        "Aw, I'm sorry to hear that. 💙 Hope things get better soon!",
        "It's okay to feel that way. Things will turn around! 💙",
        "Sending good vibes your way! 💙 You've got this.",
    ],
    ("angry", "mad", "frustrated", "annoyed", "rage"): [
        "Take a breath! 😤 Hope whatever's bothering you gets sorted.",
        "That's frustrating — hope it gets better soon!",
        "Oof, sounds rough. 😤 Want to vent?",
    ],
    ("discord", "server", "bot"): [
        "That's my home! 🤖 What do you want to do with your server?",
        "Discord is great! I can help manage your server — try `!commands`.",
        "Love Discord! Use `!commands` to see everything I can do for your server.",
    ],
    ("weather", "rain", "sunny", "cold", "hot", "snow"): [
        "I can't check the weather, but I hope it's nice where you are! ☀️",
        "Weather talk! 🌤️ Is it nice outside?",
        "Hope the weather is good! ☀️ I'm stuck inside the server anyway 😄",
    ],
}

# ============================================================
# FREEFORM CONVERSATION HANDLER
# ============================================================
def handle_freeform(text):
    t = text.lower().strip()

    # Pattern: "I like/love/enjoy X"
    m = re.search(r"i (like|love|enjoy|adore|am into|am obsessed with) (.+)", t)
    if m:
        thing = m.group(2).rstrip("!. ")
        return random.choice([
            f"Nice, {thing} is great! 😄 Tell me more.",
            f"Oh cool, {thing}! I can see why you'd enjoy that 😊",
            f"Good taste! {thing.capitalize()} is awesome 🙌",
            f"Love that you're into {thing}! What do you like most about it?",
        ])

    # Pattern: "I hate/dislike/can't stand X"
    m = re.search(r"i (hate|dislike|can't stand|don't like|dont like|am not into) (.+)", t)
    if m:
        thing = m.group(2).rstrip("!. ")
        return random.choice([
            f"Fair enough! Not everyone's into {thing}.",
            f"Understandable — {thing} isn't for everyone!",
            f"Ha, noted! Not a fan of {thing} then 😄",
        ])

    # Pattern: "I am/I'm X" (feelings/states)
    m = re.search(r"i(?:'m| am) (feeling |so |really |very )?(.+)", t)
    if m:
        state = m.group(2).rstrip("!. ")
        positive = any(w in state for w in ["happy", "good", "great", "excited", "awesome", "amazing", "well", "fine"])
        negative = any(w in state for w in ["sad", "bad", "tired", "bored", "upset", "angry", "stressed", "lonely"])
        if positive:
            return random.choice([
                f"That's awesome — glad you're {state}! 😄",
                f"Love to hear it! Keep that energy 🙌",
                f"Yay! 🎉 {state.capitalize()} looks good on you!",
            ])
        elif negative:
            return random.choice([
                f"Aw, sorry you're {state}. Hope things look up soon 💙",
                f"That's rough — hang in there! 💙",
                f"Hope you feel better soon! 💙 I'm here if you want to chat.",
            ])
        return random.choice([
            f"Oh, you're {state}? Tell me more!",
            f"Got it — {state}! How's that going?",
        ])

    # Pattern: "What is/are X"
    m = re.search(r"what(?:'s| is| are) (.+?)\??$", t)
    if m:
        subject = m.group(1).strip()
        return random.choice([
            f"Great question about {subject}! I'm a Discord bot so my knowledge is limited — try Googling it for a full answer 🔍",
            f"Hmm, {subject}... I know a bit but you'd get a better answer searching online! 🔍",
            f"I'd love to explain {subject} fully, but I'm a bot — a quick search will give you the best answer! 😊",
        ])

    # Pattern: "Who is X"
    m = re.search(r"who(?:'s| is) (.+?)\??$", t)
    if m:
        person = m.group(1).strip()
        return random.choice([
            f"I've heard of {person}! For the full story, a quick Google search is your best bet 🔍",
            f"Good question! I'm a Discord bot, so for {person} details, try searching online 🔍",
        ])

    # Pattern: "Do you like/know/think X"
    m = re.search(r"do you (like|know|think|enjoy|prefer|use|play|watch|listen) (.+?)\??$", t)
    if m:
        verb = m.group(1)
        thing = m.group(2).strip()
        if verb in ("like", "enjoy", "prefer"):
            return random.choice([
                f"As a bot I can't really {verb} things, but {thing} seems interesting! What about you?",
                f"I'd say yes if I could — {thing} sounds great! Do you {verb} it?",
            ])
        elif verb == "know":
            return random.choice([
                f"I know a bit about {thing}! Ask me something specific 😊",
                f"Some things about {thing}, yeah! What do you want to know?",
            ])
        return random.choice([
            f"Interesting question! What do *you* think about {thing}?",
            f"As a bot I'm not sure, but I'd love to hear your take on {thing}!",
        ])

    # Pattern: "What do you think about X"
    m = re.search(r"what do you think (?:about|of) (.+?)\??$", t)
    if m:
        topic = m.group(1).strip()
        return random.choice([
            f"Hmm, {topic}... I think it depends on your perspective! What's your take?",
            f"Interesting topic — {topic}! I'm a bot so no strong opinions, but I'm curious what you think 😊",
            f"I'd say {topic} has its ups and downs! What's your opinion?",
        ])

    # Pattern: "Can you X"
    m = re.search(r"can you (.+?)\??$", t)
    if m:
        action = m.group(1).strip()
        server_actions = any(w in action for w in ["ban", "kick", "create", "delete", "warn", "send", "make", "set"])
        if server_actions:
            return f"Yes I can! Try: `!ai {action}` with more details and I'll get it done 💪"
        return random.choice([
            f"I'll do my best! Try asking me directly: `!ai {action}`",
            f"Maybe! Give it a shot: `!ai {action}` 😄",
        ])

    # Pattern: questions ending in "?"
    if t.rstrip().endswith("?"):
        return random.choice([
            "Great question! I'm a Discord bot so my answers are limited, but I'll do my best 😊",
            "Hmm, tough one! I don't have all the answers but happy to chat 😄",
            "Good question! What made you think of that?",
            "Interesting! I'm not 100% sure, but I'd love to discuss it further 😊",
        ])

    # Topic keyword matching
    for keywords, responses in TOPIC_RESPONSES.items():
        if any(kw in t for kw in keywords):
            return random.choice(responses)

    # Generic statement responses
    return random.choice([
        "That's interesting! Tell me more 😊",
        "Oh really? I'd love to hear more about that!",
        "Nice! What else is on your mind?",
        "Interesting! Keep going, I'm listening 👂",
        "I see! Anything else you want to talk about?",
        "Ha, that's something! 😄 What's up with you today?",
        "Cool! You can also use `!commands` if you want to do something in the server.",
        "Word! 😄 I'm here to chat or help with server stuff — whatever you need.",
    ])

# ============================================================
# INTENT DETECTION
# ============================================================
def detect_intent(text):
    t = text.lower().strip()

    # Server management actions (check before conversation)
    if any(w in t for w in ["create channel", "make channel", "add channel", "new channel"]):
        return "create_channel"
    if any(w in t for w in ["delete channel", "remove channel", "drop channel"]):
        return "delete_channel"
    if any(w in t for w in ["create role", "make role", "new role"]):
        return "create_role"
    if any(w in t for w in ["assign role", "give role", "give the role", "add role to"]):
        return "assign_role"
    if "giveaway" in t or "give away" in t or "raffle" in t:
        return "create_giveaway"
    if "ticket" in t and any(w in t for w in ["setup", "set up", "create", "make"]):
        return "create_ticket_system"
    if any(w in t for w in ["ban "]) or t.startswith("ban "):
        return "ban_member"
    if "kick " in t or t.startswith("kick "):
        return "kick_member"
    if "warn " in t or t.startswith("warn "):
        return "warn_member"
    if any(w in t for w in ["announce", "announcement", "send announcement"]):
        return "send_announcement"
    if any(w in t for w in ["slowmode", "slow mode", "slow-mode"]):
        return "set_slowmode"
    if "welcome" in t and any(w in t for w in ["setup", "set up", "create", "make"]):
        return "setup_welcome"
    if any(w in t for w in ["custom command", "create command", "make command", "add command"]):
        return "create_custom_command"

    # Server info queries
    if any(w in t for w in ["how many member", "member count", "how many people", "how many user"]):
        return "query_members"
    if any(w in t for w in ["how many boost", "boost count", "boost level", "boosts do i"]):
        return "query_boosts"
    if any(w in t for w in ["list channel", "what channel", "show channel", "all channel"]):
        return "query_channels"
    if any(w in t for w in ["list role", "what role", "show role", "all role"]):
        return "query_roles"
    if any(w in t for w in ["server info", "server stats", "about server", "server name"]):
        return "query_server"
    if any(w in t for w in ["ping", "latency", "response time"]):
        return "ping"

    # Links and resources
    if "invite" in t and any(w in t for w in ["link", "bot", "add", "get"]):
        return "invite_link"
    if "support" in t and any(w in t for w in ["server", "link", "discord"]):
        return "support_link"
    if any(w in t for w in ["discord docs", "documentation", "discord support"]):
        return "docs_link"

    # Conversation
    if any(w in t for w in ["hello", "hi ", "hi!", "hey", "sup ", "howdy", "hiya", "what's up", "whats up", "yo "]):
        return "greeting"
    if t in ("hi", "hey", "hello", "sup", "yo"):
        return "greeting"
    if any(w in t for w in ["bye", "goodbye", "see ya", "see you", "cya", "later", "gtg"]):
        return "farewell"
    if any(w in t for w in ["how are you", "how r u", "how are u", "hows it going", "how's it going", "you doing"]):
        return "how_are_you"
    if any(w in t for w in ["thank", "thanks", "thx", "ty ", "ty!", "appreciate"]):
        return "thanks"
    if any(w in t for w in ["help", "what can you do", "what do you do"]):
        return "help"
    if any(w in t for w in ["joke", "funny", "make me laugh", "tell me a joke"]):
        return "joke"
    if any(w in t for w in ["good bot", "great bot", "nice bot", "love you", "you're great", "youre great", "amazing bot"]):
        return "compliment"

    return "unknown"

# ============================================================
# ENTITY EXTRACTORS
# ============================================================
def extract_name(text):
    for pattern in [
        r'called\s+["\']?([a-zA-Z0-9_\-]+)["\']?',
        r'named\s+["\']?([a-zA-Z0-9_\-]+)["\']?',
        r'name\s+["\']?([a-zA-Z0-9_\-]+)["\']?',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None

def extract_channel_name(text):
    m = re.search(r'in\s+#?([a-zA-Z0-9_\-]+)', text, re.IGNORECASE)
    if m:
        return m.group(1)
    return extract_name(text)

def extract_duration_hours(text):
    m = re.search(r'(\d+)\s*(day|days)\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 24
    m = re.search(r'(\d+)\s*(hour|hours|hr|hrs|h)\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*(minute|minutes|min|mins)\b', text, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)) // 60)
    return None

def extract_seconds(text):
    m = re.search(r'(\d+)\s*(second|seconds|sec|secs|s)\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # plain number
    m = re.search(r'\b(\d+)\b', text)
    if m:
        return int(m.group(1))
    return None

def extract_number(text, keywords):
    for kw in keywords:
        m = re.search(rf'(\d+)\s+{kw}', text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(rf'{kw}\s*[:\-]?\s*(\d+)', text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None

def extract_color(text):
    m = re.search(r'#([0-9a-fA-F]{6})\b', text)
    if m:
        return "#" + m.group(1)
    colors = {
        "red": "#FF0000", "blue": "#0000FF", "green": "#00FF00",
        "gold": "#FFD700", "purple": "#800080", "orange": "#FFA500",
        "pink": "#FF69B4", "white": "#FFFFFF", "black": "#000000",
        "yellow": "#FFFF00", "cyan": "#00FFFF", "gray": "#808080",
        "grey": "#808080", "blurple": "#5865F2", "teal": "#008080",
    }
    for name, hex_val in colors.items():
        if name in text.lower():
            return hex_val
    return "#5865F2"

def extract_user_id(text):
    m = re.search(r'<@!?(\d+)>', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{17,20})\b', text)
    if m:
        return m.group(1)
    return None

def extract_reason(text):
    m = re.search(r'(?:for|reason|because)\s+(.+)', text, re.IGNORECASE)
    return m.group(1).strip() if m else "No reason provided"

# ============================================================
# LOCAL AI PROCESSOR
# ============================================================
async def process_message(user_id, user_input, guild=None, bot_latency=None):
    """
    Returns (text_reply, action_obj)
    action_obj is either None, a dict (Discord action), or "help"
    """
    intent = detect_intent(user_input)
    t = user_input.lower()

    # ---- Server info queries ----
    if intent == "query_members" and guild:
        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        return f"**{guild.name}** has **{guild.member_count}** members — {humans} humans and {bots} bots.", None

    if intent == "query_boosts" and guild:
        level = guild.premium_tier
        count = guild.premium_subscription_count or 0
        needed = ([2, 7, 14][level] - count) if level < 3 else 0
        msg = f"**{guild.name}** has **{count} boosts** (Level {level})."
        if needed > 0:
            msg += f" Need **{needed}** more to reach Level {level + 1}!"
        else:
            msg += " Maximum boost level reached! 🎉"
        return msg, None

    if intent == "query_channels" and guild:
        text_chs = [f"#{c.name}" for c in guild.text_channels][:20]
        voice_chs = [f"🔊 {c.name}" for c in guild.voice_channels][:10]
        return (
            f"**Text channels ({len(guild.text_channels)}):** {', '.join(text_chs) or 'none'}\n"
            f"**Voice channels ({len(guild.voice_channels)}):** {', '.join(voice_chs) or 'none'}"
        ), None

    if intent == "query_roles" and guild:
        roles = [f"`@{r.name}`" for r in guild.roles if r.name != "@everyone"]
        return f"**Roles ({len(roles)}):** {', '.join(roles) or 'none'}", None

    if intent == "query_server" and guild:
        return (
            f"**{guild.name}**\n"
            f"👑 Owner: {guild.owner.display_name if guild.owner else 'Unknown'}\n"
            f"👥 Members: {guild.member_count}\n"
            f"📢 Channels: {len(guild.channels)}\n"
            f"🏷️ Roles: {len(guild.roles)}\n"
            f"💎 Boosts: {guild.premium_subscription_count or 0} (Level {guild.premium_tier})"
        ), None

    if intent == "ping":
        if bot_latency is not None:
            ms = round(bot_latency * 1000)
            return f"🏓 Pong! Latency: **{ms}ms**", None
        return "🏓 Pong!", None

    # ---- Links ----
    if intent == "invite_link":
        return (
            "🔗 To invite a bot, go to the **Discord Developer Portal**: https://discord.com/developers/applications\n"
            "Select your app → OAuth2 → URL Generator → choose scopes and permissions → copy the link."
        ), None

    if intent == "support_link":
        return "💬 Discord Support: https://support.discord.com\nDeveloper Docs: https://discord.com/developers/docs", None

    if intent == "docs_link":
        return "📖 Discord Developer Docs: https://discord.com/developers/docs\nDiscord Support: https://support.discord.com", None

    if intent == "help":
        return None, "help"

    # ---- Conversation ----
    if intent in RESPONSES and RESPONSES[intent] is not None:
        return random.choice(RESPONSES[intent]), None

    # ---- Server management actions ----
    if intent == "create_channel":
        name = extract_channel_name(t) or extract_name(t)
        ch_type = "voice" if "voice" in t else "category" if "category" in t else "text"
        if not name:
            return "What should the channel be called? Example: `!ai create text channel called general`", None
        return f"Creating **#{name}** ({ch_type} channel)...", {"action": "create_channel", "data": {"name": name, "type": ch_type}}

    if intent == "delete_channel":
        name = extract_channel_name(t) or extract_name(t)
        if not name:
            return "Which channel should I delete? Example: `!ai delete channel called old-chat`", None
        return f"Deleting **#{name}**...", {"action": "delete_channel", "data": {"channel_name": name}}

    if intent == "create_role":
        name = extract_name(t)
        color = extract_color(t)
        hoist = any(w in t for w in ["hoist", "display", "show separately"])
        if not name:
            return "What should the role be called? Example: `!ai create role called VIP in gold`", None
        return f"Creating role **@{name}**...", {"action": "create_role", "data": {"name": name, "color_hex": color, "hoist": hoist}}

    if intent == "create_giveaway":
        prize_m = re.search(r'(?:for|prize[:\s]+)\s*(.+?)(?:\s+in\s+#?\w+|\s+\d+\s+(?:hour|day|winner)|$)', user_input, re.IGNORECASE)
        prize = prize_m.group(1).strip() if prize_m else "Mystery Prize"
        channel = extract_channel_name(t) or "giveaway"
        duration = extract_duration_hours(t) or 24
        winners = extract_number(t, ["winner", "winners"]) or 1
        return f"🎉 Setting up giveaway for **{prize}**!", {"action": "create_giveaway", "data": {
            "channel_name": channel,
            "prize": prize,
            "duration_hours": duration,
            "winners": winners,
            "description": f"React with 🎉 for a chance to win **{prize}**!",
        }}

    if intent == "create_ticket_system":
        category = extract_name(t) or "Tickets"
        return "🎫 Setting up ticket system...", {"action": "create_ticket_system", "data": {"category_name": category}}

    if intent == "ban_member":
        uid = extract_user_id(user_input)
        if not uid:
            return "Please mention the user to ban. Example: `!ai ban @user for spamming`", None
        return f"🔨 Banning user...", {"action": "ban_member", "data": {"user_id": uid, "reason": extract_reason(t)}}

    if intent == "kick_member":
        uid = extract_user_id(user_input)
        if not uid:
            return "Please mention the user to kick. Example: `!ai kick @user for breaking rules`", None
        return f"👢 Kicking user...", {"action": "kick_member", "data": {"user_id": uid, "reason": extract_reason(t)}}

    if intent == "warn_member":
        uid = extract_user_id(user_input)
        if not uid:
            return "Please mention the user to warn. Example: `!ai warn @user for spamming`", None
        return f"⚠️ Warning user...", {"action": "warn_member", "data": {"user_id": uid, "reason": extract_reason(t)}}

    if intent == "send_announcement":
        channel = extract_channel_name(t) or "announcements"
        msg_m = re.search(r'(?:saying|message|that|:)\s+["\']?(.+)', user_input, re.IGNORECASE)
        msg_text = msg_m.group(1).strip() if msg_m else "📢 Important announcement!"
        return f"📢 Sending announcement to **#{channel}**...", {"action": "send_announcement", "data": {
            "channel_name": channel,
            "title": "📢 Announcement",
            "message": msg_text,
            "color_hex": "#5865F2",
        }}

    if intent == "set_slowmode":
        channel = extract_channel_name(t) or "general"
        seconds = extract_seconds(t) or 5
        return f"🐢 Setting slowmode to {seconds}s in **#{channel}**...", {"action": "set_slowmode", "data": {"channel_name": channel, "seconds": seconds}}

    if intent == "setup_welcome":
        channel = extract_channel_name(t) or "welcome"
        return f"👋 Setting up welcome in **#{channel}**...", {"action": "setup_welcome", "data": {
            "channel_name": channel,
            "message": "Welcome to the server, {member}! Glad to have you here! 🎉",
        }}

    if intent == "create_custom_command":
        trigger_m = re.search(r'command\s+!?(\w+)', user_input, re.IGNORECASE)
        response_m = re.search(r'(?:reply|replies|says?|respond|response)\s+["\']?(.+)', user_input, re.IGNORECASE)
        if trigger_m and response_m:
            trigger = "!" + trigger_m.group(1).lower()
            return f"✅ Creating command `{trigger}`...", {"action": "create_custom_command", "data": {
                "trigger": trigger,
                "response": response_m.group(1).strip(),
            }}
        return "Please specify trigger and response. Example: `!ai create command !hello says Hello there!`", None

    # Freeform fallback — real AI via Groq (Llama 3.1)
    reply = await ask_groq(user_id, user_input)
    return reply, None

# ============================================================
# ACTION EXECUTOR
# ============================================================
async def execute_action(guild, action_obj, channel):
    action = action_obj.get("action")
    data = action_obj.get("data", {})

    try:
        if action == "create_channel":
            ch_type = data.get("type", "text")
            category = None
            if data.get("category_name"):
                category = discord.utils.get(guild.categories, name=data["category_name"])
                if not category:
                    category = await guild.create_category(data["category_name"])
            if ch_type == "voice":
                await guild.create_voice_channel(data["name"], category=category)
            elif ch_type == "category":
                await guild.create_category(data["name"])
            else:
                await guild.create_text_channel(data["name"], topic=data.get("topic", ""), category=category)
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
            role = discord.utils.get(guild.roles, name=data["role_name"])
            if member and role:
                await member.add_roles(role)
                await channel.send(f"✅ **@{role.name}** assigned to **{member.display_name}**.")
            else:
                await channel.send("❌ Member or role not found.")

        elif action == "remove_role":
            member = guild.get_member(int(data["user_id"]))
            role = discord.utils.get(guild.roles, name=data["role_name"])
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
            end_time = utcnow() + timedelta(hours=float(data.get("duration_hours", 24)))
            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {data.get('prize', 'Mystery Prize')}",
                description=(
                    f"{data.get('description', '')}\n\n"
                    f"**Winners:** {data.get('winners', 1)}\n"
                    f"**Ends:** <t:{int(end_time.timestamp())}:R>\n\n"
                    f"React with 🎉 to enter!"
                ),
                color=discord.Color.gold(),
                timestamp=end_time
            )
            embed.set_footer(text="Ends at")
            gw_msg = await ch.send(embed=embed)
            await gw_msg.add_reaction("🎉")
            await channel.send(f"🎉 Giveaway live in **#{ch.name}**! → {gw_msg.jump_url}")

        elif action == "create_ticket_system":
            cat_name = data.get("category_name", "Tickets")
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                category = await guild.create_category(cat_name)
            support_ch = await guild.create_text_channel("open-ticket", category=category)
            embed = discord.Embed(
                title="🎫 Support Tickets",
                description="React or click below to open a support ticket!",
                color=discord.Color.blurple()
            )
            await support_ch.send(embed=embed)
            await channel.send(f"✅ Ticket system created under **{cat_name}**!")

        elif action == "send_announcement":
            ch = discord.utils.get(guild.text_channels, name=data.get("channel_name", "announcements"))
            if not ch:
                ch = await guild.create_text_channel(data.get("channel_name", "announcements"))
            color_str = data.get("color_hex", "5865F2").replace("#", "").replace("0x", "")
            embed = discord.Embed(
                title=data.get("title", "📢 Announcement"),
                description=data.get("message", ""),
                color=discord.Color(int(color_str, 16)),
                timestamp=utcnow()
            )
            await ch.send(embed=embed)
            await channel.send(f"📢 Announcement sent to **#{ch.name}**!")

        elif action == "set_slowmode":
            ch = discord.utils.get(guild.text_channels, name=data["channel_name"])
            if ch:
                await ch.edit(slowmode_delay=int(data.get("seconds", 0)))
                await channel.send(f"🐢 Slowmode set to **{data.get('seconds', 0)}s** in **#{ch.name}**.")

        elif action == "create_custom_command":
            if not hasattr(bot, "custom_commands"):
                bot.custom_commands = {}
            bot.custom_commands[data["trigger"].lower()] = data["response"]
            await channel.send(f"✅ Custom command `{data['trigger']}` created!")

        else:
            await channel.send(f"⚠️ Unknown action: `{action}`")

    except discord.Forbidden:
        await channel.send("❌ I don't have permission! Make sure I have **Administrator** role.")
    except Exception as e:
        await channel.send(f"❌ Error: `{e}`")

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your server 👁️"))

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        embed = discord.Embed(
            title=f"👋 Welcome to {member.guild.name}!",
            description=f"Hey {member.mention}, glad to have you!\nYou are member **#{member.guild.member_count}**.",
            color=discord.Color.green(),
            timestamp=utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if hasattr(bot, "custom_commands"):
        for trigger, response in bot.custom_commands.items():
            if message.content.lower().startswith(trigger):
                await message.channel.send(response)
                return
    await bot.process_commands(message)

# ============================================================
# MAIN AI COMMAND
# ============================================================
@bot.command(name="ai", aliases=["agent", "a"])
async def ai_agent(ctx, *, user_input: str):
    user_id = ctx.author.id

    # Per-user cooldown
    now = utcnow()
    last = user_last_called.get(user_id)
    if last and (now - last).total_seconds() < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last).total_seconds())
        await ctx.send(f"⏳ Please wait **{remaining}s** before using `!ai` again.")
        return
    user_last_called[user_id] = now

    async with ctx.typing():
        text_reply, action_obj = await process_message(user_id, user_input, guild=ctx.guild, bot_latency=bot.latency)

        if action_obj == "help":
            await ctx.invoke(bot.get_command("commands"))
            return

        if text_reply:
            await ctx.send(text_reply)

        if action_obj and isinstance(action_obj, dict):
            await execute_action(ctx.guild, action_obj, ctx.channel)

@bot.command(name="reset")
async def reset(ctx):
    conversation_history.pop(ctx.author.id, None)
    await ctx.send("🔄 Conversation reset! I've forgotten our chat history.")

# ============================================================
# DIRECT MOD COMMANDS
# ============================================================
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 **{member}** banned. Reason: {reason}")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** kicked.")

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    embed = discord.Embed(
        title="⚠️ Warning",
        description=f"**Server:** {ctx.guild.name}\n**Reason:** {reason}",
        color=discord.Color.yellow()
    )
    try:
        await member.send(embed=embed)
    except Exception:
        pass
    await ctx.send(f"⚠️ **{member}** warned.")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Cleared **{amount}** messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int = 0):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"🐢 Slowmode set to **{seconds}s**." if seconds else "✅ Slowmode off.")

@bot.command(name="ping")
async def ping(ctx):
    ms = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{ms}ms**")

@bot.command(name="commands")
async def show_commands(ctx):
    embed = discord.Embed(title="🤖 Bot Commands", color=discord.Color.blurple())
    embed.add_field(name="🧠 AI Agent", value=(
        "`!ai hello` — Chat with the bot\n"
        "`!ai how many members` — Server info\n"
        "`!ai create channel called general` — Create channel\n"
        "`!ai create role called VIP in gold` — Create role\n"
        "`!ai giveaway for Nitro in #giveaway 24 hours 1 winner` — Giveaway\n"
        "`!ai ban @user for spamming` — Ban member\n"
        "`!ai setup ticket system` — Ticket system\n"
        "`!ai announce in #general saying Hello!` — Announcement\n"
        "`!ai ping` — Bot latency"
    ), inline=False)
    embed.add_field(name="🛡️ Moderation", value=(
        "`!ban @user [reason]`\n"
        "`!kick @user [reason]`\n"
        "`!warn @user [reason]`\n"
        "`!clear [amount]`\n"
        "`!slowmode [seconds]`"
    ), inline=False)
    embed.add_field(name="🔧 Utility", value="`!ping` — Latency\n`!reset` — Reset session", inline=False)
    embed.set_footer(text="No API needed — fully self-contained ⚡")
    await ctx.send(embed=embed)

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)
