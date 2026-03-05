"""
Discord bot: schedule images -> DM -> parse shifts -> approve -> Google Calendar.
Single-process, SQLite for tokens + dedupe.
"""

import json
import logging
import os
import re
from dotenv import load_dotenv
import discord

from db import (
    clear_pending,
    get_pending,
    init_db,
    is_processed,
    load_gcal_token,
    mark_processed,
    set_pending,
)
from parser import Shift, parse_shifts, shifts_hash
from calendar_client import create_events

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("DISCORD_TOKEN")
SCHEDULE_CHANNEL_ID = int(os.getenv("SCHEDULE_CHANNEL_ID", "0"))
MY_DISCORD_USER_ID = int(os.getenv("MY_DISCORD_USER_ID", "0"))
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

IMAGE_RE = re.compile(r"\.(png|jpg|jpeg|webp)$", re.IGNORECASE)

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

client = discord.Client(intents=intents)


def _shift_to_str(s: Shift) -> str:
    return f"{s.day} {s.start}-{s.end}" + (" (overnight)" if s.overnight else "")


def _format_review(shifts: list, warnings: list) -> str:
    lines = ["**Parsed shifts:**"]
    for s in shifts:
        lines.append(f"• {_shift_to_str(s)}")
    if warnings:
        lines.append("\n**Warnings:**")
        for w in warnings:
            lines.append(f"⚠ {w}")
    lines.append("\nReply **approve** to add to Google Calendar, or **edit** to resend shifts.")
    return "\n".join(lines)


@client.event
async def on_ready():
    init_db()
    logger.info("Logged in as %s (id=%s)", client.user, client.user.id)
    logger.info("SCHEDULE_CHANNEL_ID=%s MY_DISCORD_USER_ID=%s", SCHEDULE_CHANNEL_ID, MY_DISCORD_USER_ID)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ----- DM from me -----
    if isinstance(message.channel, discord.DMChannel) and message.author.id == MY_DISCORD_USER_ID:
        content = (message.content or "").strip().lower()
        pending = get_pending(MY_DISCORD_USER_ID)

        if content == "approve":
            if not pending or pending["state"] != "awaiting_approval":
                await message.author.send("No shifts pending approval. Send your shifts first.")
                return

            shifts_data = json.loads(pending["shifts_json"])
            shifts = [Shift(**s) for s in shifts_data]
            msg_id = pending["message_id"]
            shash = shifts_hash(shifts)

            if is_processed(msg_id, shash):
                clear_pending(MY_DISCORD_USER_ID)
                await message.author.send("Already processed this schedule. No duplicate events created.")
                return

            token_json = load_gcal_token(MY_DISCORD_USER_ID)
            if not token_json:
                await message.author.send(
                    "Google Calendar not authorized. Run `python auth_gcal.py` first, then try again."
                )
                return

            created, err = create_events(shifts, TIMEZONE, token_json)
            clear_pending(MY_DISCORD_USER_ID)

            if err:
                await message.author.send(f"Failed to create events: {err}")
                return

            mark_processed(msg_id, shash)
            summary_lines = [f"• {e['summary']} @ {e['start']}" for e in created]
            await message.author.send(
                f"✅ Created {len(created)} event(s) on your Google Calendar:\n" + "\n".join(summary_lines)
            )
            logger.info("Created %d events for user %s", len(created), MY_DISCORD_USER_ID)
            return

        if content == "edit":
            if pending:
                set_pending(MY_DISCORD_USER_ID, pending["message_id"], pending["shifts_json"], "awaiting_shifts")
            await message.author.send("Send your shifts again (e.g. Mon 4-9, Wed 5-10pm).")
            return

        # Treat as shift text
        shifts, warnings = parse_shifts(message.content)
        if not shifts:
            await message.author.send(
                "I couldn't parse any shifts. Use format like: `Mon 4-9, Wed 5-10pm`\n"
                "Reply **edit** if you had a pending approval and want to resend."
            )
            return

        msg_id = pending["message_id"] if pending else 0
        set_pending(
            MY_DISCORD_USER_ID,
            msg_id,
            json.dumps([{"day": s.day, "start": s.start, "end": s.end, "overnight": s.overnight} for s in shifts]),
            "awaiting_approval",
        )
        await message.author.send(_format_review(shifts, warnings))
        return

    # ----- Channel message (schedule image) -----
    if SCHEDULE_CHANNEL_ID and message.channel.id != SCHEDULE_CHANNEL_ID:
        return

    image_url = None
    for att in message.attachments:
        if att.content_type and att.content_type.startswith("image/"):
            image_url = att.url
            break
        if att.filename and IMAGE_RE.search(att.filename):
            image_url = att.url
            break

    if not image_url:
        return

    # Dedupe: we can't know shifts until user replies, so we store pending by message_id
    # and only mark processed when approved. For "same image reposted" dedupe: we use
    # message_id + shifts_hash. Duplicate = same message_id would mean same image.
    # But each new post has new message_id. So dedupe kicks in when: user replies with
    # shifts, we get hash, then if they approve we mark (message_id, hash). If they
    # post a NEW image (new message_id) and reply with SAME shifts, we'd create dupes
    # because message_id differs. The spec says: "reposting the same schedule image"
    # - that implies same message? Or same image content? For MVP: same message_id +
    # same shifts_hash = duplicate. So we only mark processed on approve. If user
    # posts image A, we DM. They reply with shifts X. We store pending. They approve.
    # We mark (msg_A_id, hash(X)). If they post image B (different msg), reply same X,
    # approve -> we'd create again. The spec says "reposting the same schedule image"
    # - I'll interpret as: if we already processed (message_id, shifts_hash) skip.
    # When we get the image, we don't have shifts yet. So we can't dedupe at image
    # stage. We dedupe at approve: before creating, check is_processed(msg_id, hash).
    # If already processed, don't create and tell user.

    logger.info("Schedule image detected: msg_id=%s channel_id=%s %s", message.id, message.channel.id, image_url)

    set_pending(MY_DISCORD_USER_ID, message.id, "[]", "awaiting_shifts")

    try:
        user = await client.fetch_user(MY_DISCORD_USER_ID)
        await user.send(
            f"I detected a schedule image in <#{message.channel.id}>.\n"
            f"Reply with your shifts like: `Mon 4-9, Wed 5-10pm`"
        )
        logger.info("DM sent successfully to user %s", MY_DISCORD_USER_ID)
    except discord.Forbidden as e:
        logger.error("Cannot DM user %s (Forbidden): %s. User may have DMs disabled from server members.", MY_DISCORD_USER_ID, e)
    except Exception as e:
        logger.exception("Failed to send DM: %s", e)


if __name__ == "__main__":
    logger.info("Starting bot... TOKEN present=%s", bool(TOKEN))
    client.run(TOKEN)
