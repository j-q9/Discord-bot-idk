# AI Discord Server Manager Bot

## Overview
A self-contained Discord bot that lets server owners manage their server through natural language — no external AI API required. Uses a built-in rule-based engine to understand commands, answer questions, and execute Discord actions.

## Tech Stack
- **Language:** Python 3.12
- **Discord Library:** discord.py 2.3.2
- **AI:** Built-in rule-based engine (no external API)

## Project Structure
- `bot.py` — All bot logic: local AI engine, action executor, Discord commands
- `requirements.txt` — Python dependencies (discord.py only)

## Environment Variables / Secrets
- `DISCORD_TOKEN` — Discord bot token (from Discord Developer Portal)

## Running the Bot
The bot runs as a console workflow: `python bot.py`

## Bot Commands
- `!ai <anything>` — Chat with the built-in AI (no API key needed)
- `!ping` — Show bot latency
- `!reset` — Reset session
- `!ban @user [reason]` — Ban a member
- `!kick @user [reason]` — Kick a member
- `!warn @user [reason]` — Warn a member via DM
- `!clear [amount]` — Purge messages
- `!slowmode [seconds]` — Set slowmode
- `!commands` — Show all commands

## AI Capabilities (via !ai)
- **Conversation:** greetings, questions, jokes, compliments
- **Server info:** member count, boost info, channels, roles, server stats
- **Links:** Discord docs, support, invite info
- **Actions:** create/delete channels & roles, ban/kick/warn, giveaways, tickets, announcements, slowmode, custom commands, welcome system
