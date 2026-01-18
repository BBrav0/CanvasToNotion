# Canvas → Notion Assignment Sync

Syncs your Canvas LMS assignments to your Notion database.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get your API tokens

**Canvas API Token:**
1. Go to Canvas → Account → Settings
2. Scroll to "Approved Integrations"
3. Click "+ New Access Token"
4. Give it a name, generate, copy the token

**Notion Integration Token:**
1. Go to https://www.notion.so/profile/integrations
2. Click "+ New integration"
3. Name it (e.g., "Canvas Sync")
4. Copy the "Internal Integration Secret"

**Important:** Share your Notion database with the integration!
1. Open your Assignments database in Notion
2. Click ••• in the top right → "Connections"
3. Add your integration

### 3. Configure environment
```bash
cp .env.example .env
```

Edit `.env` and fill in your tokens:
```
CANVAS_KEY=your_canvas_token_here
NOTION_KEY=your_notion_token_here
NOTION_DB=2e683dcb1f8f80daa7fac80cde473efa
```

### 4. Update course mappings

In `sync.py`, update the `normalize_course_name()` function to map your Canvas course names to your Notion "Course" select options.

### 5. Run it
```bash
python sync.py
```

## Automate (optional)

Run it daily with cron:
```bash
crontab -e
```

Add this line to run at 8am every day:
```
0 8 * * * cd /path/to/canvas_to_notion && python sync.py >> sync.log 2>&1
```

## Your Notion Database Schema

| Column | Type | Notes |
|--------|------|-------|
| Assignment | Title | Assignment name |
| Due Date | Date | Due date/time |
| Course | Select | Your course options |
| Completed | Checkbox | Mark when done |
