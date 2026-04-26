# RadhaKrishnaPhoto.in Automation Setup Guide

## Overview

This is an adapted WordPress post automation system tailored for your photography website **radhakrishnaphoto.in**. It automatically generates and publishes gallery-style posts based on photography keywords, optimized for SEO and user engagement.

**Key Features:**
- ✅ Automatic post generation from keywords
- ✅ Beautiful gallery layouts with images
- ✅ Smart slug & title management
- ✅ Progress tracking (resume from where you left off)
- ✅ Telegram notifications
- ✅ Internal linking for SEO
- ✅ Dry-run mode for testing

---

## Files Overview

| File | Purpose |
|------|---------|
| `auto_posts.py` | Main automation script (the engine) |
| `keywords.txt` | Photography keywords (one per line) |
| `intros.txt` | Intro paragraph templates (separated by ---) |
| `meta_descriptions.txt` | Meta description templates |
| `title_templates.txt` | Post title templates |
| `subheading_fallbacks.txt` | Fallback subheadings for galleries |
| `used_keywords.txt` | Tracks progress (auto-created) |
| `logs/auto_posts.log` | Execution logs (auto-created) |

---

## Installation Steps

### 1. Prerequisites

- Python 3.7+ installed
- Access to radhakrishnaphoto.in WordPress admin
- WordPress REST API enabled (usually enabled by default)

### 2. Get WordPress App Password

1. Login to radhakrishnaphoto.in WordPress admin
2. Go to **Users** → **Your Profile**
3. Scroll to **Application Passwords** section
4. Create a new app password called "Auto Posts"
5. Copy the generated password (format: `xxxx xxxx xxxx xxxx xxxx`)

### 3. Set Environment Variables

Store your credentials securely as environment variables:

**On Linux/Mac:**
```bash
export WP_USERNAME="your_wordpress_username"
export WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

**On Windows (PowerShell):**
```powershell
$env:WP_USERNAME="your_wordpress_username"
$env:WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx"
$env:TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
$env:TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

**Or create a `.env` file and source it before running:**
```
WP_USERNAME=your_wordpress_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 4. Install Python Dependencies

```bash
pip install requests
```

---

## Configuration

Edit `auto_posts.py` to customize:

```python
# How many posts per run
POSTS_PER_RUN = 2

# How many posts per keyword (using different title templates)
POSTS_PER_KEYWORD = 5

# Images per subheading section
IMAGES_PER_HEADING = 10

# Post status: "draft" for testing, "publish" for production
POST_STATUS = "publish"

# Gap between posts (randomized from list)
POST_GAP_OPTIONS_SECONDS = [
    30 * 60,    # 30 minutes
    45 * 60,    # 45 minutes
    60 * 60,    # 1 hour
    # ...
]
```

**For RadhaKrishnaPhoto.in:**
- Categories are auto-detected: Krishna Photography, Temple Photography, Festival Photography, etc.
- Images are pulled from your WordPress media library automatically
- Recent posts are linked internally for SEO

---

## How It Works

### The Process

1. **Load Progress**: Checks `used_keywords.txt` to see where we left off
2. **Fetch Categories**: Gets all WordPress categories
3. **Build Queue**: Creates a list of (keyword, post_number) pairs to publish
4. **For Each Post:**
   - Generate unique title (from templates)
   - Generate unique slug
   - Fetch or generate subheadings
   - Build HTML gallery with images
   - Create WordPress post via REST API
   - Track progress

### Post Structure

Each post auto-generates:
- **Intro paragraph** (from templates with {keyword} replaced)
- **Multiple H2 sections** with images (subheadings)
- **Images** (randomly selected from your media library)
- **Internal links** to recent posts (for SEO)
- **Meta description** (optimized for search engines)
- **Focus keyword** (set in Yoast SEO)

### Progress Tracking

Progress is saved as `used_keywords.txt`:
```
keyword1::3of5        # keyword1 has 3 out of 5 posts published
keyword2              # keyword2 is fully completed (5 posts)
```

Next run automatically resumes from post 4 for keyword1.

---

## Running the Script

### Test Run (Dry Run)

Preview without publishing:
```bash
python auto_posts.py --dry-run --skip-sleep
```

Output will show what **would** be published, without actually creating posts.

### Live Run

Publish 2 posts:
```bash
python auto_posts.py
```

Publish custom number:
```bash
python auto_posts.py --posts 1
```

Publish without startup sleep:
```bash
python auto_posts.py --skip-sleep
```

---

## Telegram Notifications

The script sends updates to Telegram after each run.

### Set Up Telegram Bot

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get bot token
3. Start a chat with your bot
4. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
5. Set environment variables (see Installation Step 3)

Notifications include:
- ✅ Posts created (with links)
- ❌ Posts failed
- ⏭️ Posts skipped
- Total time taken
- Startup/execution details

---

## Customizing Content

### Keywords

Edit `keywords.txt` to add your photography keywords:

```
Krishna photography beautiful
Lord Krishna temple photography
Temple photography India
Divine Krishna darshan
Festival photography India
```

**Tip:** Start with 10-15 broad keywords. The script will generate 5 posts per keyword (50-75 total posts).

### Intros

Edit `intros.txt`. Each intro is separated by `---`:

```
Discover stunning {keyword} photography that captures divine moments. Our professional gallery showcases...

---

Explore our exquisite collection of {keyword} photographs. Each image...

---
```

The `{keyword}` placeholder is replaced with the current keyword automatically.

### Titles

Edit `title_templates.txt`. One template per line:

```
[COUNT]+ {keyword} Photography Images HD 2025
Best {keyword} Photography | Stunning Gallery Collection
Professional {keyword} Photography Gallery
```

**Special Tags:**
- `{keyword}` → replaced with seed keyword
- `[COUNT]+` → replaced with random number (50-999)

### Meta Descriptions

Edit `meta_descriptions.txt` for SEO meta tags (max 155 chars):

```
Explore beautiful {keyword} photography gallery. Professional high-quality images...

---

Stunning {keyword} photography collection featuring professional images...
```

### Subheading Fallbacks

Edit `subheading_fallbacks.txt` for H2 section headings:

```
Best Collection, Professional Gallery, Stunning Images, Sacred Moments, Artistic Expression
Temple Photography, Festival Celebration, Spiritual Art, Devotional Moments, Sacred Beauty
```

Each line is a comma-separated set. One random set is chosen per post, then 5 subheadings are selected from it.

---

## Scheduling (Automation)

To run automatically every day:

### Linux/Mac (cron)

```bash
crontab -e
```

Add:
```bash
# Run every day at 9 AM
0 9 * * * cd /path/to/script && python auto_posts.py >> cron.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 9 AM
4. Set action: Start program
5. Program: `python.exe`
6. Arguments: `C:\path\to\auto_posts.py`

### Docker (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.9
WORKDIR /app
COPY . /app
RUN pip install requests
CMD ["python", "auto_posts.py"]
```

Build and run:
```bash
docker build -t radha-photography-automation .
docker run -e WP_USERNAME=... -e WP_APP_PASSWORD=... radha-photography-automation
```

---

## Troubleshooting

### Posts Not Publishing

**Check WordPress credentials:**
```bash
python auto_posts.py --dry-run
```

If it fails at category fetching, check:
1. WP_USERNAME and WP_APP_PASSWORD are correct
2. App password is generated in WordPress (Users → Profile)
3. REST API is enabled

### Duplicate Title Error

Titles already exist for that keyword. The script skips the post.

**Solution:** Add more title templates to `title_templates.txt`

### Slug Already Exists

All slug variations already exist.

**Solution:** Add more variations to `SLUG_VARIATIONS` list in the script

### No Images

Media not fetched from WordPress.

**Solution:**
1. Ensure you have images uploaded to radhakrishnaphoto.in
2. Check WordPress credentials (media fetch requires auth)
3. Test with `--dry-run` to see mock media

### Telegram Not Sending

Check:
1. `TELEGRAM_BOT_TOKEN` is set correctly
2. `TELEGRAM_CHAT_ID` is set correctly
3. Bot has permission to message you

Test with:
```python
python -c "from auto_posts import send_telegram; send_telegram('Test')"
```

---

## Monitoring

### Check Logs

```bash
cat logs/auto_posts.log
```

Or tail in real-time:
```bash
tail -f logs/auto_posts.log
```

### Check Used Keywords

```bash
cat used_keywords.txt
```

Example output:
```
krishna photography beautiful::2of5
lord krishna temple photography
temple photography india::1of5
```

---

## SEO Optimization Tips

1. **Keywords**: Use long-tail keywords (3-5 words) for better ranking
2. **Images**: Ensure good image alt text in WordPress media library
3. **Categories**: Organize posts into relevant categories
4. **Meta Descriptions**: Make them compelling (155 characters)
5. **Internal Links**: Recent posts are auto-linked for SEO
6. **Titles**: Include keyword in title but keep it natural

---

## Example Workflow

### Day 1: Setup
1. Install Python and requests
2. Get WordPress app password
3. Create Telegram bot (optional but recommended)
4. Set environment variables
5. Customize keywords, titles, intros, descriptions
6. Run `python auto_posts.py --dry-run` to test

### Day 2-7: Test & Adjust
1. Run `python auto_posts.py --posts 1` (publish 1 post)
2. Check radhakrishnaphoto.in to see the published post
3. Adjust templates if needed
4. Run again: `python auto_posts.py` (publish 2 more)

### Week 2+: Automate
1. Set up cron/Task Scheduler to run daily
2. Monitor logs and Telegram notifications
3. Add new keywords as needed
4. Watch rankings improve!

---

## Key Differences from Pixlino Version

This version is optimized for photography:

| Aspect | Pixlino | RadhaKrishnaPhoto |
|--------|---------|-------------------|
| Niche | Girl DP / Images | Photography |
| Categories | Girl DP types | Photography types |
| Fallback subheadings | Image-focused | Photography-focused |
| Intro templates | Image-centric | Gallery/art-centric |
| Meta descriptions | Image gallery tone | Professional photography tone |
| Keywords | Face-based | Subject-based (Krishna, temples, etc.) |

---

## Support

### Common Commands

```bash
# Dry run with skip sleep
python auto_posts.py --dry-run --skip-sleep

# Publish 1 post
python auto_posts.py --posts 1

# Publish 5 posts with no startup sleep
python auto_posts.py --posts 5 --skip-sleep

# View logs
tail -f logs/auto_posts.log

# Reset progress (start over)
rm used_keywords.txt
```

### Reset All Progress

To start fresh:
```bash
rm used_keywords.txt logs/auto_posts.log
```

This will process all keywords from the start on next run.

---

## Disclaimer

- Always test with `--dry-run` before going live
- Ensure your images have proper alt text for SEO
- Monitor WordPress performance with large post volumes
- Adjust `POSTS_PER_RUN` if server struggles
- Keep WordPress and plugins updated

---

**Happy automating! 📸🚀**
