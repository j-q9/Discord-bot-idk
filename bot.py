import discord
from discord.ext import commands
import asyncio
import json
import re
import os
from datetime import datetime, timedelta, timezone
import aiohttp

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ============================================================
# CONFIG
# ============================================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
PREFIX        = "!"
COOLDOWN_SECONDS = 5

# ============================================================
# INTENTS
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds  = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ============================================================
# STATE  (in-memory — resets on bot restart)
# ============================================================
user_last_called     = {}   # user_id  -> datetime
conversation_history = {}   # user_id  -> list of {role, content}
auto_role_config     = {}   # guild_id -> role_name
welcome_config       = {}   # guild_id -> {channel_name, message}
farewell_config      = {}   # guild_id -> {channel_name, message}
word_filter          = {}   # guild_id -> set of words

# ============================================================
# GROQ AI
# ============================================================
GROQ_SYSTEM_PROMPT = """You are an AI-powered Discord server manager bot. You can chat about ANYTHING and also manage Discord servers.

WHEN THE USER WANTS A SERVER ACTION, respond ONLY with a valid JSON object on one line, no markdown, no explanation:
{"action": "ACTION_NAME", "data": {...}}

Available actions:
- ban_member            {"user_id": "ID", "reason": "..."}
- kick_member           {"user_id": "ID", "reason": "..."}
- mute_member           {"user_id": "ID", "duration_minutes": 10, "reason": "..."}
- warn_member           {"user_id": "ID", "reason": "..."}
- change_nickname       {"user_id": "ID", "nickname": "new name"}
- create_channel        {"name": "...", "type": "text|voice|category|announcement|forum", "category_name": "optional"}
- delete_channel        {"channel_name": "..."}
- rename_channel        {"old_name": "...", "new_name": "..."}
- create_role           {"name": "...", "color_hex": "#5865F2", "hoist": false}
- delete_role           {"role_name": "..."}
- assign_role           {"user_id": "ID", "role_name": "..."}
- remove_role_from_user {"user_id": "ID", "role_name": "..."}
- set_auto_role         {"role_name": "..."}
- disable_auto_role     {}
- setup_welcome         {"channel_name": "welcome", "message": "Welcome {member} to {server}!"}
- setup_farewell        {"channel_name": "general", "message": "Goodbye {member}!"}
- add_word_filter       {"words": ["word1", "word2"]}
- remove_word_filter    {"words": ["word1"]}
- send_announcement     {"channel_name": "announcements", "title": "...", "message": "...", "color_hex": "#5865F2"}
- set_slowmode          {"channel_name": "...", "seconds": 5}
- create_giveaway       {"channel_name": "giveaway", "prize": "...", "duration_hours": 24, "winners": 1}
- purge_user_messages   {"user_id": "ID", "filter": "all|images|links|text", "limit": 100}
- query_members         {}
- query_channels        {}
- query_roles           {}
- query_server          {}

User mentions look like <@123456789012345678>. Extract only the digits as user_id.

For EVERYTHING ELSE (chat, questions, jokes, opinions, general talk) — respond naturally, short (1-3 sentences), casual and friendly tone, occasional emojis."""


async def ask_groq(user_id, message):
    if not GROQ_API_KEY:
        return "⚠️ No GROQ_API_KEY set — add it in Secrets!"

    history  = conversation_history.get(user_id, [])
    messages = [{"role": "system", "content": GROQ_SYSTEM_PROMPT}]
    messages += history[-10:]
    messages.append({"role": "user", "content": message})

    payload = {
        "model":       "llama-3.1-8b-instant",
        "messages":    messages,
        "max_tokens":  300,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 429:
                    return "⏳ Rate-limited — try again in a moment!"
                if resp.status in (401, 403):
                    body = await resp.text()
                    print(f"Groq auth error {resp.status}: {body}")
                    return "❌ Invalid GROQ_API_KEY. Check your Secrets."
                if resp.status != 200:
                    body = await resp.text()
                    print(f"Groq HTTP {resp.status}: {body}")
                    return f"❌ Groq error ({resp.status}). Try again."

                result = await resp.json()
                reply  = result["choices"][0]["message"]["content"].strip()

        h = conversation_history.setdefault(user_id, [])
        h.append({"role": "user",      "content": message})
        h.append({"role": "assistant", "content": reply})
        conversation_history[user_id] = h[-20:]
        return reply

    except asyncio.TimeoutError:
        return "⏳ AI is taking too long — try again in a moment!"
    except Exception as ex:
        print(f"Groq error: {ex}")
        return "❌ Couldn't reach AI right now. Try again."

# ============================================================
# PROCESS MESSAGE
# ============================================================
async def process_message(user_id, user_input, guild=None, bot_latency=None):
    """Returns (text_reply, action_obj_or_None)."""

    # Hidden easter egg
    if re.sub(r"[^a-z]", "", user_input.lower()) in ("whoisgay", "whosgay"):
        if guild:
            target = discord.utils.find(
                lambda m: "miloparade" in m.name.lower() or "miloparade" in m.display_name.lower(),
                guild.members
            )
            if target:
                return target.mention, None
        return "@miloparade", None

    raw = await ask_groq(user_id, user_input)

    # Try to parse as a JSON server action
    try:
        cleaned = raw.strip()
        # Strip markdown fences if present
        cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()

        if cleaned.startswith("{"):
            obj = json.loads(cleaned)
            if "action" in obj:
                action = obj["action"]
                data   = obj.get("data", {})

                # Handle query actions locally with live Discord data
                if guild:
                    if action == "query_members":
                        bots   = sum(1 for m in guild.members if m.bot)
                        humans = guild.member_count - bots
                        return (
                            f"**{guild.name}** has **{guild.member_count}** members "
                            f"— {humans} humans, {bots} bots."
                        ), None

                    if action == "query_channels":
                        text_ch  = [f"#{c.name}" for c in guild.text_channels][:15]
                        voice_ch = [f"🔊 {c.name}" for c in guild.voice_channels][:10]
                        return (
                            f"**Text ({len(guild.text_channels)}):** {', '.join(text_ch) or 'none'}\n"
                            f"**Voice ({len(guild.voice_channels)}):** {', '.join(voice_ch) or 'none'}"
                        ), None

                    if action == "query_roles":
                        roles = [f"`@{r.name}`" for r in guild.roles if r.name != "@everyone"]
                        return f"**Roles ({len(roles)}):** {', '.join(roles) or 'none'}", None

                    if action == "query_server":
                        return (
                            f"**{guild.name}**\n"
                            f"👑 Owner: {guild.owner.display_name if guild.owner else 'Unknown'}\n"
                            f"👥 Members: {guild.member_count}\n"
                            f"📢 Channels: {len(guild.channels)}\n"
                            f"🏷️ Roles: {len(guild.roles)}\n"
                            f"💎 Boosts: {guild.premium_subscription_count or 0} (Level {guild.premium_tier})"
                        ), None

                return None, obj

    except (json.JSONDecodeError, ValueError):
        pass

    # Plain text — just chat
    return raw, None

# ============================================================
# ACTION EXECUTOR
# ============================================================
async def execute_action(guild, action_obj, channel):
    action = action_obj.get("action", "")
    data   = action_obj.get("data", {})

    try:
        # ── Moderation ──────────────────────────────────────────
        if action == "ban_member":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            await member.ban(reason=data.get("reason", "No reason provided"))
            await channel.send(
                f"🔨 **{member.display_name}** has been banned. "
                f"Reason: {data.get('reason', 'N/A')}"
            )

        elif action == "kick_member":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            await member.kick(reason=data.get("reason", "No reason provided"))
            await channel.send(
                f"👢 **{member.display_name}** has been kicked. "
                f"Reason: {data.get('reason', 'N/A')}"
            )

        elif action == "mute_member":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            minutes = int(data.get("duration_minutes", 10))
            until   = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            await member.timeout(until, reason=data.get("reason", "No reason provided"))
            await channel.send(
                f"🔇 **{member.display_name}** muted for **{minutes} minutes**. "
                f"Reason: {data.get('reason', 'N/A')}"
            )

        elif action == "warn_member":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            embed = discord.Embed(
                title="⚠️ Warning",
                description=f"**Server:** {guild.name}\n**Reason:** {data.get('reason', 'No reason')}",
                color=discord.Color.yellow()
            )
            try:
                await member.send(embed=embed)
            except Exception:
                pass
            await channel.send(
                f"⚠️ **{member.display_name}** warned. "
                f"Reason: {data.get('reason', 'N/A')}"
            )

        elif action == "change_nickname":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            old_nick = member.display_name
            new_nick = data.get("nickname") or None
            await member.edit(nick=new_nick)
            await channel.send(
                f"✏️ Nickname changed: **{old_nick}** → **{new_nick or '(reset to username)'}**"
            )

        # ── Channels ─────────────────────────────────────────────
        elif action == "create_channel":
            ch_type = data.get("type", "text").lower()
            name    = data.get("name", "new-channel")
            category = None
            if data.get("category_name"):
                category = discord.utils.get(guild.categories, name=data["category_name"])
                if not category:
                    category = await guild.create_category(data["category_name"])

            if ch_type == "voice":
                ch = await guild.create_voice_channel(name, category=category)
                await channel.send(f"✅ Voice channel **{ch.name}** created!")

            elif ch_type == "category":
                cat = await guild.create_category(name)
                await channel.send(f"✅ Category **{cat.name}** created!")

            elif ch_type == "announcement":
                ch = await guild.create_text_channel(name, category=category)
                try:
                    await ch.edit(type=discord.ChannelType.news)
                    await channel.send(f"📢 Announcement channel **#{ch.name}** created!")
                except Exception:
                    await channel.send(
                        f"✅ Channel **#{ch.name}** created! "
                        "(Announcement type requires a Community server)"
                    )

            elif ch_type == "forum":
                try:
                    ch = await guild.create_forum(name, category=category)
                    await channel.send(f"💬 Forum channel **#{ch.name}** created!")
                except Exception:
                    ch = await guild.create_text_channel(name, category=category)
                    await channel.send(
                        f"✅ Channel **#{ch.name}** created! "
                        "(Forum type requires a Community server)"
                    )

            else:
                ch = await guild.create_text_channel(name, category=category)
                await channel.send(f"✅ Text channel **#{ch.name}** created!")

        elif action == "delete_channel":
            ch = discord.utils.get(guild.channels, name=data.get("channel_name", ""))
            if not ch:
                return await channel.send(f"❌ Channel **#{data.get('channel_name')}** not found.")
            name = ch.name
            await ch.delete()
            await channel.send(f"🗑️ Channel **#{name}** deleted.")

        elif action == "rename_channel":
            ch = discord.utils.get(guild.channels, name=data.get("old_name", ""))
            if not ch:
                return await channel.send(f"❌ Channel **#{data.get('old_name')}** not found.")
            await ch.edit(name=data["new_name"])
            await channel.send(
                f"✏️ Channel renamed: **#{data['old_name']}** → **#{data['new_name']}**"
            )

        # ── Roles ─────────────────────────────────────────────────
        elif action == "create_role":
            color_hex = data.get("color_hex", "#5865F2").replace("#", "")
            color = discord.Color(int(color_hex, 16))
            role  = await guild.create_role(
                name=data["name"], color=color, hoist=data.get("hoist", False)
            )
            await channel.send(f"✅ Role **@{role.name}** created!")

        elif action == "delete_role":
            role = discord.utils.get(guild.roles, name=data.get("role_name", ""))
            if not role:
                return await channel.send(f"❌ Role **@{data.get('role_name')}** not found.")
            name = role.name
            await role.delete()
            await channel.send(f"🗑️ Role **@{name}** deleted.")

        elif action == "assign_role":
            member = guild.get_member(int(data["user_id"]))
            role   = discord.utils.get(guild.roles, name=data.get("role_name", ""))
            if not member or not role:
                return await channel.send("❌ Member or role not found.")
            await member.add_roles(role)
            await channel.send(f"✅ **@{role.name}** given to **{member.display_name}**.")

        elif action == "remove_role_from_user":
            member = guild.get_member(int(data["user_id"]))
            role   = discord.utils.get(guild.roles, name=data.get("role_name", ""))
            if not member or not role:
                return await channel.send("❌ Member or role not found.")
            await member.remove_roles(role)
            await channel.send(f"✅ **@{role.name}** removed from **{member.display_name}**.")

        elif action == "set_auto_role":
            role_name = data.get("role_name", "")
            auto_role_config[guild.id] = role_name
            await channel.send(
                f"✅ Auto-role set to **@{role_name}**! "
                "Every new member will automatically receive this role."
            )

        elif action == "disable_auto_role":
            auto_role_config.pop(guild.id, None)
            await channel.send("✅ Auto-role has been disabled.")

        # ── Welcome / Farewell ────────────────────────────────────
        elif action == "setup_welcome":
            welcome_config[guild.id] = {
                "channel_name": data.get("channel_name", "welcome"),
                "message":      data.get("message", "Welcome {member} to {server}!"),
            }
            await channel.send(
                f"✅ Welcome messages enabled in **#{data.get('channel_name', 'welcome')}**!"
            )

        elif action == "setup_farewell":
            farewell_config[guild.id] = {
                "channel_name": data.get("channel_name", "general"),
                "message":      data.get("message", "Goodbye {member}!"),
            }
            await channel.send(
                f"✅ Farewell messages enabled in **#{data.get('channel_name', 'general')}**!"
            )

        # ── Word Filter ───────────────────────────────────────────
        elif action == "add_word_filter":
            words = [w.lower() for w in data.get("words", [])]
            if not words:
                return await channel.send("❌ No words provided.")
            word_filter.setdefault(guild.id, set()).update(words)
            await channel.send(
                f"🚫 **{len(words)}** word(s) added to the filter. "
                "Messages containing them will be auto-deleted."
            )

        elif action == "remove_word_filter":
            words = [w.lower() for w in data.get("words", [])]
            if guild.id in word_filter:
                word_filter[guild.id] -= set(words)
            await channel.send(f"✅ **{len(words)}** word(s) removed from the filter.")

        # ── Utility ───────────────────────────────────────────────
        elif action == "send_announcement":
            ch_name = data.get("channel_name", "announcements")
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if not ch:
                ch = await guild.create_text_channel(ch_name)
            color_hex = data.get("color_hex", "5865F2").replace("#", "")
            embed = discord.Embed(
                title=data.get("title", "📢 Announcement"),
                description=data.get("message", ""),
                color=discord.Color(int(color_hex, 16)),
                timestamp=utcnow()
            )
            await ch.send(embed=embed)
            await channel.send(f"📢 Announcement sent to **#{ch.name}**!")

        elif action == "set_slowmode":
            ch = discord.utils.get(guild.text_channels, name=data.get("channel_name", ""))
            if not ch:
                return await channel.send(f"❌ Channel **#{data.get('channel_name')}** not found.")
            secs = int(data.get("seconds", 0))
            await ch.edit(slowmode_delay=secs)
            await channel.send(f"🐢 Slowmode set to **{secs}s** in **#{ch.name}**.")

        elif action == "purge_user_messages":
            member = guild.get_member(int(data["user_id"]))
            if not member:
                return await channel.send("❌ Member not found in this server.")
            filter_type = data.get("filter", "all").lower()
            limit       = min(int(data.get("limit", 100)), 500)

            def check(m):
                if m.author.id != member.id:
                    return False
                if filter_type == "images":
                    return bool(m.attachments) or any(
                        ext in m.content.lower()
                        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov"]
                    )
                if filter_type == "links":
                    return bool(re.search(r"https?://", m.content))
                if filter_type == "text":
                    return not m.attachments and not re.search(r"https?://", m.content)
                return True  # "all"

            deleted = await channel.purge(limit=limit, check=check)
            label = {
                "images": "image/video",
                "links":  "link",
                "text":   "text-only",
                "all":    "",
            }.get(filter_type, "")
            await channel.send(
                f"🗑️ Deleted **{len(deleted)}** {label+' ' if label else ''}message(s) from **{member.display_name}**.",
                delete_after=10
            )

        elif action == "create_giveaway":
            ch_name = data.get("channel_name", "giveaways")
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if not ch:
                ch = await guild.create_text_channel(ch_name)
            end_time = utcnow() + timedelta(hours=float(data.get("duration_hours", 24)))
            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {data.get('prize', 'Mystery Prize')}",
                description=(
                    f"React with 🎉 to enter!\n\n"
                    f"**Winners:** {data.get('winners', 1)}\n"
                    f"**Ends:** <t:{int(end_time.timestamp())}:R>"
                ),
                color=discord.Color.gold(),
                timestamp=end_time
            )
            embed.set_footer(text="Ends at")
            msg = await ch.send(embed=embed)
            await msg.add_reaction("🎉")
            await channel.send(f"🎉 Giveaway live in **#{ch.name}**! → {msg.jump_url}")

        else:
            await channel.send(f"⚠️ Unknown action: `{action}`")

    except discord.Forbidden:
        await channel.send(
            "❌ Missing permissions! Make sure I have the **Administrator** role."
        )
    except Exception as e:
        print(f"execute_action error ({action}): {e}")
        await channel.send(f"❌ Error: `{e}`")

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="your server 👁️"
    ))

@bot.event
async def on_member_join(member):
    guild = member.guild

    # Auto-role
    role_name = auto_role_config.get(guild.id)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            try:
                await member.add_roles(role)
            except Exception:
                pass

    # Welcome message
    cfg = welcome_config.get(guild.id)
    if cfg:
        ch = discord.utils.get(guild.text_channels, name=cfg["channel_name"])
        if ch:
            msg = (
                cfg["message"]
                .replace("{member}", member.mention)
                .replace("{server}", guild.name)
            )
            embed = discord.Embed(
                description=msg,
                color=discord.Color.green(),
                timestamp=utcnow()
            )
            embed.set_author(
                name=f"Welcome to {guild.name}!",
                icon_url=member.display_avatar.url
            )
            await ch.send(embed=embed)
    else:
        # Default welcome (if no config but channel exists)
        ch = discord.utils.get(guild.text_channels, name="welcome")
        if ch:
            embed = discord.Embed(
                title=f"👋 Welcome to {guild.name}!",
                description=(
                    f"Hey {member.mention}, glad to have you here! "
                    f"You're member **#{guild.member_count}**."
                ),
                color=discord.Color.green(),
                timestamp=utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild = member.guild
    cfg   = farewell_config.get(guild.id)
    if cfg:
        ch = discord.utils.get(guild.text_channels, name=cfg["channel_name"])
        if ch:
            msg = (
                cfg["message"]
                .replace("{member}", member.display_name)
                .replace("{server}", guild.name)
            )
            embed = discord.Embed(
                description=msg,
                color=discord.Color.red(),
                timestamp=utcnow()
            )
            embed.set_author(
                name="Member left",
                icon_url=member.display_avatar.url
            )
            await ch.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Word filter — auto-delete censored messages
    if message.guild and message.guild.id in word_filter:
        content_lower = message.content.lower()
        if any(w in content_lower for w in word_filter[message.guild.id]):
            try:
                await message.delete()
                await message.channel.send(
                    f"🚫 {message.author.mention} Your message was removed — it contained a filtered word.",
                    delete_after=5
                )
            except Exception:
                pass
            return

    await bot.process_commands(message)

# ============================================================
# COMMANDS
# ============================================================
@bot.command(name="ai", aliases=["agent", "a"])
async def ai_agent(ctx, *, user_input: str):
    user_id = ctx.author.id
    now     = utcnow()
    last    = user_last_called.get(user_id)
    if last and (now - last).total_seconds() < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last).total_seconds())
        await ctx.send(f"⏳ Please wait **{remaining}s** before using `!ai` again.")
        return
    user_last_called[user_id] = now

    async with ctx.typing():
        text_reply, action_obj = await process_message(
            user_id, user_input, guild=ctx.guild, bot_latency=bot.latency
        )
        if text_reply:
            await ctx.send(text_reply)
        if action_obj and isinstance(action_obj, dict):
            await execute_action(ctx.guild, action_obj, ctx.channel)

@bot.command(name="reset")
async def reset(ctx):
    conversation_history.pop(ctx.author.id, None)
    await ctx.send("🔄 Chat history cleared!")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! **{round(bot.latency * 1000)}ms**")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Cleared **{amount}** messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="commands")
async def show_commands(ctx):
    embed = discord.Embed(
        title="🤖 AI Server Manager",
        description=(
            "Just tell me what you want in plain English using `!ai`.\n"
            "No commands to memorise — the AI understands you."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(name="🛡️ Moderation", value=(
        "`!ai ban @user for spamming`\n"
        "`!ai kick @user`\n"
        "`!ai mute @user for 10 minutes`\n"
        "`!ai warn @user for being rude`\n"
        "`!ai change @user's nickname to CoolName`"
    ), inline=False)
    embed.add_field(name="📢 Channels", value=(
        "`!ai create text channel called general`\n"
        "`!ai create voice channel called Music`\n"
        "`!ai create announcement channel called news`\n"
        "`!ai create forum channel called help`\n"
        "`!ai rename channel old-name to new-name`\n"
        "`!ai delete channel called old-chat`"
    ), inline=False)
    embed.add_field(name="🏷️ Roles", value=(
        "`!ai create role called VIP in gold`\n"
        "`!ai delete role called Member`\n"
        "`!ai give @user the VIP role`\n"
        "`!ai set auto role to Member`"
    ), inline=False)
    embed.add_field(name="👋 Welcome & Farewell", value=(
        "`!ai set up welcome messages in #welcome`\n"
        "`!ai set up farewell message in #general`"
    ), inline=False)
    embed.add_field(name="🗑️ Message Purge", value=(
        "`!ai delete all messages from @user`\n"
        "`!ai remove @user image only`\n"
        "`!ai purge @user links`\n"
        "`!ai clear @user text messages`"
    ), inline=False)
    embed.add_field(name="🚫 Word Filter", value=(
        "`!ai filter the words: bad, word2`\n"
        "`!ai remove badword from the filter`"
    ), inline=False)
    embed.add_field(name="🔧 Utility", value=(
        "`!ai send announcement in #news saying Hello everyone!`\n"
        "`!ai set slowmode to 10 seconds in #general`\n"
        "`!ai start a giveaway for Nitro in #giveaway for 24 hours`\n"
        "`!clear 20` — delete messages\n"
        "`!reset` — clear your chat history\n"
        "`!ping` — bot latency"
    ), inline=False)
    embed.set_footer(text="Powered by Groq AI (Llama 3.1) ⚡")
    await ctx.send(embed=embed)

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)
