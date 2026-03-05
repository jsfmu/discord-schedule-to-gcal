import os
import re
import discord
from dotenv import load_dotenv

load_dotenv()

print("=== BOT.PY STARTED ===")
print("TOKEN present?", bool(os.getenv("DISCORD_TOKEN")))
print("CHANNEL ID:", os.getenv("SCHEDULE_CHANNEL_ID"))
print("USER ID:", os.getenv("MY_DISCORD_USER_ID"))

TOKEN = os.getenv("DISCORD_TOKEN")
SCHEDULE_CHANNEL_ID = int(os.getenv("SCHEDULE_CHANNEL_ID", "0"))
MY_DISCORD_USER_ID = int(os.getenv("MY_DISCORD_USER_ID", "0"))

IMAGE_RE = re.compile(r"\.(png|jpg|jpeg|webp)$", re.IGNORECASE)

intents = discord.Intents.default()
intents.message_content = True  # also enable Message Content Intent in Dev Portal

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (id={client.user.id})")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

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

    print("Schedule image detected:", image_url)

    user = await client.fetch_user(MY_DISCORD_USER_ID)
    await user.send(
        f"I saw a schedule image in <#{message.channel.id}>.\n"
        f"Image: {image_url}\n"
        f"Reply with shifts like: `Mon 4-9, Wed 5-10`"
    )

print("About to start Discord client...")
client.run(TOKEN)