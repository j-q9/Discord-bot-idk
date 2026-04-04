# AI Discord Server Manager Bot

## Overview
An AI-powered Discord bot that lets server owners manage their Discord server through natural language conversation. It uses Claude AI (Anthropic) to interpret requests and execute administrative actions automatically.

## Tech Stack
- **Language:** Python 3.12
- **Discord Library:** discord.py 2.3.2
- **AI:** Anthropic Claude (claude-sonnet-4-20250514)

## Project Structure
- `bot.py` — All bot logic: AI integration, action executor, Discord commands
- `requirements.txt` — Python dependencies

## Environment Variables / Secrets
- `DISCORD_TOKEN` — Discord bot token (from Discord Developer Portal)
- `ANTHROPIC_API_KEY` — Anthropic API key (from console.anthropic.com)

## Running the Bot
The bot runs as a console workflow: `python bot.py`

## Bot Commands
- `!ai <request>` — Natural language server management via Claude AI
- `!reset` — Reset conversation history
- `!ban @user [reason]` — Ban a member
- `!kick @user [reason]` — Kick a member
- `!warn @user [reason]` — Warn a member via DM
- `!clear [amount]` — Purge messages
- `!slowmode [seconds]` — Set slowmode
- `!commands` — Show all commands

## AI-Powered Actions
The bot can create/delete channels, manage roles, ban/kick/warn members, set up welcome systems, create giveaways, ticket systems, announcements, and custom commands — all via `!ai <natural language>`.
