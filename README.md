# discord-schedule-to-gcal

MVP: Discord schedule images → parse shifts from DM reply → create Google Calendar events.

## Setup

### 1. Virtual environment and dependencies

```powershell
cd c:\Users\jsfmu\discord-schedule-to-gcal
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Discord bot

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications).
2. Enable **Message Content Intent** under Bot settings.
3. Copy the bot token.

### 3. Discord channel and user IDs

1. Enable Developer Mode: User Settings → App Settings → Advanced → Developer Mode.
2. Right‑click the channel → Copy ID.
3. Right‑click your user → Copy ID.

### 4. Environment variables

```powershell
copy .env.example .env
```

Edit `.env`:

```
DISCORD_TOKEN=your_bot_token
SCHEDULE_CHANNEL_ID=channel_id_number
MY_DISCORD_USER_ID=your_discord_user_id
TIMEZONE=America/Los_Angeles
```

### 5. Google Calendar OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable **Google Calendar API**.
3. Configure OAuth consent screen (External, add your email as test user).
4. Create OAuth 2.0 credentials → Desktop app.
5. Download JSON and save as `credentials.json` in the project root.

### 6. One-time auth

```powershell
.venv\Scripts\activate
python auth_gcal.py
```

Sign in in the browser and approve Calendar access. The token is stored in `data.db`.

## Run the bot

```powershell
.venv\Scripts\activate
python -u bot.py
```

## Flow

1. Post an image in the schedule channel → bot DMs you.
2. Reply with shifts (e.g. `Mon 4-9, Wed 5-10pm`).
3. Bot sends a review and asks for **approve** or **edit**.
4. Reply **approve** → events created on your primary Google Calendar.
5. Reply **edit** → bot asks you to resend shifts.

## Notes

- If end time is earlier than start time, treated as overnight (end next day).
- Missing AM/PM assumed PM (with a warning in the review).
- Deduplication: same schedule image + same parsed shifts won't create duplicate events.
