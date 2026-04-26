"""
auto_posts.py — Fully Automatic WordPress Post Creator for RadhaKrishnaPhoto.in (v20)
=======================================================================================
Adapted from Pixlino automation for photography/Krishna theme website

Changes from v19:
  ✅ POSTS_PER_KEYWORD = 5  — each keyword gets exactly 5 posts (different title templates)
  ✅ POSTS_PER_RUN = 2      — only 2 posts published per day/run
  ✅ Keyword marked as used ONLY after all 5 posts for it are published
  ✅ Partial progress tracked in used_keywords.txt as "keyword::3of5" style
  ✅ On next run, resumes from where it left off for that keyword

File structure:
  auto_posts.py              ← this script
  keywords.txt               ← your seed keywords (one per line)
  intros.txt                 ← intro templates (blocks split by ---)
  meta_descriptions.txt      ← meta desc templates (blocks split by ---)
  title_templates.txt        ← title templates (one per line)
  subheading_fallbacks.txt   ← fallback sets (one set per line, comma separated)
"""

import requests
import random
import re
import time
import argparse
import os
from datetime import datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

WP_URL             = "https://radhakrishnaphoto.in/wp-json/wp/v2"
USERNAME           = os.environ.get("WP_USERNAME", "your_wp_username")
APP_PASSWORD       = os.environ.get("WP_APP_PASSWORD", "your_app_password")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "your_token")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "your_chat_id")

# --- Post settings ---
POSTS_PER_RUN      = 2            # how many posts to publish per run (per day)
POSTS_PER_KEYWORD  = 5            # how many posts to create for each keyword (uses different title templates)
IMAGES_PER_HEADING = 10           # images per heading
POST_STATUS        = "publish"      # ← TEST MODE: saving as draft (change back to "publish" for production)

# --- Random gap options (in seconds) ---
POST_GAP_OPTIONS_SECONDS = [
    30 * 60,    # 30 minutes
    45 * 60,    # 45 minutes
    60 * 60,    # 1 hour
    75 * 60,    # 1 hour 15 minutes
    90 * 60,    # 1 hour 30 minutes
    105 * 60,   # 1 hour 45 minutes
    120 * 60,   # 2 hours
]

# --- Random startup sleep range (seconds) ---
STARTUP_SLEEP_MIN = 0
STARTUP_SLEEP_MAX = 30 * 60

# --- Slug variation words (tried in order if base slug already exists) ---
SLUG_VARIATIONS = ["photography", "gallery", "new", "latest", "best", "hd", "4k"]

# --- Words to remove from slug ---
SLUG_REMOVE_WORDS = {
    "free", "download", "watch"
}

# --- Fallback category ---
FALLBACK_CATEGORY = "Photography"

# --- All content files ---
KEYWORDS_FILE            = "keywords.txt"
INTROS_FILE              = "intros.txt"
META_DESCRIPTIONS_FILE   = "meta_descriptions.txt"
TITLE_TEMPLATES_FILE     = "title_templates.txt"
SUBHEADING_FALLBACK_FILE = "subheading_fallbacks.txt"

# --- Tracking files ---
USED_KEYWORDS_FILE = "used_keywords.txt"
LOG_FILE           = "logs/auto_posts.log"

# --- Low keywords warning threshold ---
LOW_KEYWORDS_THRESHOLD = 10

AUTH = (USERNAME, APP_PASSWORD)


# ============================================================
# RUN STATS
# ============================================================

class RunStats:
    def __init__(self):
        self.start_time     = datetime.now()
        self.posts_created  = []
        self.posts_failed   = []
        self.posts_skipped  = []
        self.keywords_used  = []
        self.dry_run        = False
        self.gap_seconds    = 0
        self.startup_sleep  = 0

    def elapsed(self):
        delta = datetime.now() - self.start_time
        hours = int(delta.total_seconds() // 3600)
        mins  = int((delta.total_seconds() % 3600) // 60)
        secs  = int(delta.total_seconds() % 60)
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        return f"{mins}m {secs}s"


STATS = RunStats()


# ============================================================
# HELPERS
# ============================================================

def seconds_to_human(seconds):
    hours = int(seconds // 3600)
    mins  = int((seconds % 3600) // 60)
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"


# ============================================================
# LOGGING
# ============================================================

def log(msg):
    os.makedirs("logs", exist_ok=True)
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================================================
# FILE LOADERS
# ============================================================

def load_text_list(filepath, split_by="---"):
    if not os.path.exists(filepath):
        log(f"  ⚠ File not found: {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if split_by:
        entries = [e.strip() for e in content.split(split_by) if e.strip()]
    else:
        entries = [
            line.strip() for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    log(f"  Loaded {len(entries)} entries from {filepath}")
    return entries


def load_subheading_fallbacks():
    lines  = load_text_list(SUBHEADING_FALLBACK_FILE, split_by=None)
    result = []
    for line in lines:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if parts:
            result.append(parts)
    log(f"  Loaded {len(result)} subheading fallback sets")
    return result


def load_keywords_from_file():
    seeds = load_text_list(KEYWORDS_FILE, split_by=None)
    log(f"  Loaded {len(seeds)} seed keywords from {KEYWORDS_FILE}")
    return seeds


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("  ⚠ Telegram not configured — skipping notification")
        return

    if len(message) > 4000:
        message = message[:3997] + "..."

    url    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }

    try:
        r = requests.post(url, data=params, timeout=15)
        if r.status_code == 200:
            log("  ✓ Telegram notification sent")
        else:
            log(f"  ✗ Telegram failed (HTTP {r.status_code})")
    except Exception as e:
        log(f"  ✗ Telegram error: {e}")


# ============================================================
# WORDPRESS API
# ============================================================

def fetch_wp_categories():
    """Fetch all categories from WordPress"""
    try:
        url = f"{WP_URL}/categories?per_page=100"
        r = requests.get(url, auth=AUTH, timeout=30)
        if r.status_code == 200:
            cats = r.json()
            log(f"  Fetched {len(cats)} categories from WordPress")
            return cats
        else:
            log(f"  ✗ Failed to fetch categories (HTTP {r.status_code})")
            return []
    except Exception as e:
        log(f"  ✗ Error fetching categories: {e}")
        return []


def fetch_all_wp_media(per_page=100):
    """Fetch all media from WordPress"""
    all_media = []
    page = 1
    while True:
        try:
            url = f"{WP_URL}/media?per_page={per_page}&page={page}"
            r = requests.get(url, auth=AUTH, timeout=30)
            if r.status_code == 200:
                items = r.json()
                if not items:
                    break
                all_media.extend(items)
                page += 1
            else:
                break
        except Exception as e:
            log(f"  ✗ Error fetching media (page {page}): {e}")
            break

    log(f"  Fetched {len(all_media)} media items from WordPress")
    return all_media


def fetch_existing_titles():
    """Fetch all existing post titles to avoid duplicates"""
    try:
        titles = set()
        page = 1
        while True:
            url = f"{WP_URL}/posts?per_page=100&page={page}&status=publish,draft"
            r = requests.get(url, auth=AUTH, timeout=30)
            if r.status_code == 200:
                posts = r.json()
                if not posts:
                    break
                for post in posts:
                    titles.add(post["title"]["rendered"].strip().lower())
                page += 1
            else:
                break
        log(f"  Fetched {len(titles)} existing post titles")
        return titles
    except Exception as e:
        log(f"  ✗ Error fetching existing titles: {e}")
        return set()


def fetch_recent_posts_for_links(count=5):
    """Fetch recent posts for internal linking"""
    try:
        url = f"{WP_URL}/posts?per_page={count}&status=publish&orderby=date&order=desc"
        r = requests.get(url, auth=AUTH, timeout=30)
        if r.status_code == 200:
            posts = r.json()
            result = [
                {
                    "title": p["title"]["rendered"],
                    "link": p["link"],
                }
                for p in posts
            ]
            log(f"  Fetched {len(result)} recent posts for internal linking")
            return result
        else:
            log(f"  ✗ Failed to fetch recent posts (HTTP {r.status_code})")
            return []
    except Exception as e:
        log(f"  ✗ Error fetching recent posts: {e}")
        return []


def post_exists(slug):
    """Check if a post with this slug already exists"""
    try:
        url = f"{WP_URL}/posts?slug={slug}"
        r = requests.get(url, auth=AUTH, timeout=15)
        if r.status_code == 200:
            posts = r.json()
            return len(posts) > 0
        else:
            return False
    except Exception as e:
        log(f"  ✗ Error checking slug: {e}")
        return False


def create_wp_post(title, slug, html_content, category_id, focus_kw, meta_desc):
    """Create a post in WordPress"""
    try:
        url = f"{WP_URL}/posts"
        data = {
            "title":            title,
            "slug":             slug,
            "content":          html_content,
            "status":           POST_STATUS,
            "categories":       [category_id] if category_id else [],
            "meta": {
                "focus_keyphrase": focus_kw,
            },
            "yoast_head_json": {
                "description": meta_desc,
            }
        }

        r = requests.post(url, json=data, auth=AUTH, timeout=60)

        if r.status_code in [200, 201]:
            post_data = r.json()
            post_id = post_data.get("id")
            post_link = post_data.get("link")
            log(f"  ✓ Post created successfully (ID={post_id})")
            return post_id, post_link
        else:
            log(f"  ✗ Failed to create post (HTTP {r.status_code})")
            try:
                error_data = r.json()
                log(f"  Error details: {error_data}")
            except:
                log(f"  Response: {r.text[:200]}")
            return None, None

    except Exception as e:
        log(f"  ✗ Exception creating post: {e}")
        return None, None


# ============================================================
# CONTENT GENERATION
# ============================================================

def generate_focus_keyword(keyword):
    """Generate focus keyword from seed keyword"""
    return keyword.strip()


def generate_intro(keyword):
    """Generate intro paragraph"""
    intros = load_text_list(INTROS_FILE)
    if not intros:
        return f"Discover beautiful {keyword} photography and gallery collections."
    intro_template = random.choice(intros)
    return intro_template.replace("{keyword}", keyword)


def generate_meta_description(keyword):
    """Generate meta description"""
    meta_descs = load_text_list(META_DESCRIPTIONS_FILE)
    if not meta_descs:
        return f"Explore stunning {keyword} photos. High-quality gallery of {keyword} images."
    meta_template = random.choice(meta_descs)
    return meta_template.replace("{keyword}", keyword)[:155]


def fetch_subheadings_from_google(keyword, count=5):
    """Fetch subheadings (fallback system)"""
    fallbacks = load_subheading_fallbacks()
    if not fallbacks:
        # Default subheadings for photography
        return [
            f"Best {keyword} Photography",
            f"Professional {keyword} Gallery",
            f"{keyword.title()} Collections",
            f"{keyword.title()} Picture Ideas",
            f"Latest {keyword} Shots",
        ]
    chosen = random.choice(fallbacks)
    return chosen[:count]


def generate_unique_title(keyword, title_templates, existing_titles, used_templates):
    """Generate unique title from templates"""
    templates = title_templates or [
        "[COUNT]+ {keyword} Photos HD 2025",
        "Best {keyword} Photography | Gallery",
        "{keyword} Pictures Collection",
        "{keyword} Images HD Quality",
        "Beautiful {keyword} Shots",
    ]

    candidates = []
    for template in templates:
        if template in used_templates:
            continue

        # Replace {keyword} placeholder
        title = template.replace("{keyword}", keyword)

        # Replace [COUNT]+ with random number if present
        if "[COUNT]+" in title:
            count = random.randint(50, 999)
            title = title.replace("[COUNT]+", f"{count}+")

        candidates.append((title, template))

    if not candidates:
        # Fallback: just use keyword with counter
        count = random.randint(100, 999)
        title = f"{count}+ {keyword} Photos HD 2025"
        candidates = [(title, "[fallback]")]

    # Pick first candidate that doesn't exist
    for title, template in candidates:
        title_lower = title.strip().lower()
        if title_lower not in existing_titles:
            return title, template, True

    # All tried titles exist
    return candidates[0][0], candidates[0][1], False


def make_safe_slug(text):
    """Convert text to safe WordPress slug"""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    text = re.sub(r"-+", "-", text)
    return text


def get_unique_slug(keyword):
    """Get a unique slug for the keyword"""
    base_slug = make_safe_slug(keyword)

    # Remove blacklisted words
    for word in SLUG_REMOVE_WORDS:
        base_slug = base_slug.replace(word, "").replace("--", "-")

    base_slug = base_slug.strip("-")

    # Check if it exists
    if not post_exists(base_slug):
        return base_slug, True

    # Try variations
    for variation in SLUG_VARIATIONS:
        slug = f"{base_slug}-{variation}"
        if not post_exists(slug):
            return slug, True

    # All variations exist
    return base_slug, False


def get_unique_title(keyword, existing_titles, used_templates_for_kw):
    """Get a unique title for the keyword"""
    title_templates = load_text_list(TITLE_TEMPLATES_FILE, split_by=None)
    title, template_used, ok = generate_unique_title(keyword, title_templates, existing_titles, used_templates_for_kw)
    return title, template_used, ok


def match_category(title, categories):
    """Match post title to the most relevant category"""
    if not categories:
        return None

    title_lower = title.lower()

    # Try keyword matching
    for cat in categories:
        cat_name = cat.get("name", "").lower()
        if cat_name in title_lower:
            return cat["id"]

    # Default to first category
    return categories[0]["id"] if categories else None


def build_html_gallery(subheadings, media_items, images_per_heading, keyword, intro, recent_posts=None, current_title=""):
    """Build HTML gallery with subheadings and images"""
    html = []

    # Intro paragraph
    html.append(f"<p><em>{intro}</em></p>")

    # Gallery sections
    for subheading in subheadings:
        html.append(f"<h2>{subheading}</h2>")

        # Add images for this subheading
        selected_media = random.sample(media_items, min(images_per_heading, len(media_items)))
        for media in selected_media:
            img_id = media.get("id")
            img_url = media.get("source_url")
            alt_text = media.get("alt_text", keyword)

            html.append(
                f'<figure class="wp-block-image">'
                f'<img src="{img_url}" alt="{alt_text}" data-id="{img_id}" />'
                f'<figcaption>{alt_text}</figcaption>'
                f'</figure>'
            )

        # Add paragraph between sections
        html.append(f"<p>Explore more stunning {subheading.lower()} in our gallery collection.</p>")

    # Internal links section
    if recent_posts:
        html.append("<h3>Related Photography Collections</h3>")
        html.append("<ul>")
        for post in recent_posts:
            if post.get("link") and post.get("title") != current_title:
                html.append(f'<li><a href="{post["link"]}">{post["title"]}</a></li>')
        html.append("</ul>")

    # Conclusion
    html.append(f"<p>Thank you for exploring our {keyword} photography gallery. Share your favorite images!</p>")

    return "\n".join(html)


# ============================================================
# KEYWORD TRACKING
# ============================================================

def load_used_keywords():
    """Load keyword progress from tracking file"""
    result = {}
    if not os.path.exists(USED_KEYWORDS_FILE):
        return result

    with open(USED_KEYWORDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "::" in line:
                kw, progress = line.split("::")
                kw = kw.strip().lower()
                try:
                    count = int(progress.split("of")[0])
                    result[kw] = count
                except:
                    result[kw] = 0
            else:
                result[line.lower()] = POSTS_PER_KEYWORD

    return result


def save_keyword_progress(keyword, count_done):
    """Save keyword progress"""
    kw_lower = keyword.lower()

    # Load current state
    state = load_used_keywords()
    state[kw_lower] = count_done

    # Write back
    with open(USED_KEYWORDS_FILE, "w", encoding="utf-8") as f:
        for kw, count in sorted(state.items()):
            if count >= POSTS_PER_KEYWORD:
                f.write(f"{kw}\n")
            else:
                f.write(f"{kw}::{count}of{POSTS_PER_KEYWORD}\n")

    log(f"  Saved progress: {keyword} ({count_done}/{POSTS_PER_KEYWORD})")


def collect_keywords(used_keywords_dict):
    """Build queue of (keyword, post_number) tuples"""
    seeds = load_keywords_from_file()
    queue = []

    for kw in seeds:
        kw_lower = kw.lower()
        count_done = used_keywords_dict.get(kw_lower, 0)

        for post_num in range(count_done + 1, POSTS_PER_KEYWORD + 1):
            queue.append((kw, post_num))

    # Check if we have few keywords left
    unique_keywords = len(set(seeds))
    keywords_to_complete = len(set(kw for kw, _ in queue))

    if keywords_to_complete < LOW_KEYWORDS_THRESHOLD:
        log(f"⚠️  WARNING: Only {keywords_to_complete} keywords remaining!")

    return queue


# ============================================================
# MAIN RUN FUNCTION
# ============================================================

def build_telegram_summary(stats):
    """Build Telegram summary message"""
    duration = stats.elapsed()
    start_time = stats.start_time.strftime("%d %b %Y, %I:%M %p")

    summary = f"""
<b>🤖 Auto Posts Report</b>
<b>Date:</b> {start_time}
<b>Mode:</b> {'🧪 DRY RUN' if stats.dry_run else '🚀 LIVE RUN'}
<b>Time Taken:</b> {duration}

<b>📊 Summary</b>
✅ Posts Created : {len(stats.posts_created)}
❌ Posts Failed  : {len(stats.posts_failed)}
⏭️  Posts Skipped : {len(stats.posts_skipped)}

<b>📝 Posts Created:</b>
"""

    for i, post in enumerate(stats.posts_created, 1):
        summary += (
            f"\n{i}. <b>{post['title']}</b>"
            f"\n   📂 {post['category']} | 🔑 {post['keyword']}"
            f"\n   🔗 <a href=\"{post['link']}\">{post['link']}</a>\n"
        )

    if stats.posts_failed:
        summary += "\n<b>❌ Failed Posts:</b>\n"
        for fail in stats.posts_failed:
            summary += f"  • {fail}\n"

    summary += (
        f"\n<b>🔧 Automation Info:</b>"
        f"\n  Time: {stats.start_time.strftime('%d %b %Y, %I:%M %p')}"
    )

    return summary


def run(posts_to_create=POSTS_PER_RUN, dry_run=False, skip_sleep=False):
    """Main automation run"""
    STATS.dry_run = dry_run
    STATS.posts_per_run = posts_to_create

    # ── Startup sleep ──────────────────────────────────────────
    if not skip_sleep and not dry_run:
        startup_sleep = random.randint(STARTUP_SLEEP_MIN, STARTUP_SLEEP_MAX)
        STATS.startup_sleep = startup_sleep
        gap_human = seconds_to_human(startup_sleep)
        log(f"Starting in {gap_human}... (scheduled at {datetime.now().strftime('%I:%M %p')})")
        log(
            f"Time: {STATS.start_time.strftime('%d %b %Y, %I:%M %p')}"
        )

        if startup_sleep > 0:
            time.sleep(startup_sleep)
            log(f"  Startup sleep done. Actual start: {datetime.now().strftime('%I:%M %p')}")
    else:
        log(
            f"Time: {STATS.start_time.strftime('%d %b %Y, %I:%M %p')}"
        )

    # ── Random gap between posts ──────────────────────────────
    gap_seconds = random.choice(POST_GAP_OPTIONS_SECONDS)
    gap_human = seconds_to_human(gap_seconds)
    STATS.gap_seconds = gap_seconds
    log(f"Gap between posts: {gap_human}")

    # ── Load state ────────────────────────────────────────────
    used_keywords_dict = load_used_keywords()
    log(f"Loaded progress for {len(used_keywords_dict)} keywords from {USED_KEYWORDS_FILE}")

    # ── Categories ────────────────────────────────────────────
    log("Fetching WordPress categories...")
    categories = fetch_wp_categories() if not dry_run else [
        {"id": 1, "name": "Radha Krishna Wallpaper"},
        {"id": 2, "name": "Radha Krishna Photo"},
        {"id": 3, "name": "Radha Krishna Images"},
        {"id": 4, "name": "Radha Krishna Drawing"},
        {"id": 5, "name": "Radha Rani"},
    ]

    if not categories:
        msg = "❌ ERROR: Could not fetch WordPress categories. Check your credentials."
        log(msg)
        send_telegram(msg)
        return

    # ── Build queue ───────────────────────────────────────────
    log("Building post queue from keywords...")
    queue = collect_keywords(used_keywords_dict)

    if not queue:
        msg = (
            "🚨 <b>No posts remaining!</b>\n\n"
            "All keywords in <code>keywords.txt</code> have been fully processed.\n"
            "Please add new keywords and push to GitHub."
        )
        log("Queue empty. Exiting.")
        send_telegram(msg)
        return

    # Select posts_to_create items from the queue (in order — don't shuffle,
    # so we always complete lower post numbers first)
    selected = queue[:posts_to_create]
    STATS.keywords_used = [kw for kw, _ in selected]
    log(f"Selected {len(selected)} post slots for this run")
    for kw, n in selected:
        log(f"  → '{kw}' (post {n}/{POSTS_PER_KEYWORD})")

    # ── Media ─────────────────────────────────────────────────
    if not dry_run:
        all_media = fetch_all_wp_media()
        if not all_media:
            msg = "❌ ERROR: Could not fetch WP media. Check your credentials."
            log(msg)
            send_telegram(msg)
            return
    else:
        all_media = [
            {"id": i, "source_url": f"https://radhakrishnaphoto.in/wp-content/img{i}.jpg", "alt_text": "photography"}
            for i in range(1, 500)
        ]

    existing_titles = fetch_existing_titles() if not dry_run else set()

    # ── Fetch recent posts for internal linking (once per run) ───
    recent_posts_for_links = fetch_recent_posts_for_links(count=5) if not dry_run else [
        {"title": "Radha Krishna Photo", "link": "https://radhakrishnaphoto.in/radha-krishna-love-black-wallpaper/"},
        {"title": "Radha Rani", "link": "https://radhakrishnaphoto.in/radha-rani-photo-hd-1080p/"},
        {"title": "Radha Krishna Wallpaper", "link": "https://radhakrishnaphoto.in/radha-krishna-wallpaper/"},
    ]

    # ── Track in-run progress per keyword ────────────────────
    # keyword_lower → count of posts successfully published this run
    in_run_published = {}

    # ── Main loop ─────────────────────────────────────────────
    for i, (kw, post_num) in enumerate(selected):
        log(f"\n--- Post {i+1}/{len(selected)} | Keyword: '{kw}' | Post {post_num}/{POSTS_PER_KEYWORD} ---")

        # Step 1: Title (avoid templates already used for this keyword)
        used_templates_for_kw = []  # could extend to load from file if needed
        title, template_used, title_ok = get_unique_title(kw, existing_titles, used_templates_for_kw)
        if not title_ok:
            send_telegram(
                f"⏭️ <b>Post Skipped — Duplicate Title</b>\n\n"
                f"🔑 Keyword: <b>{kw}</b> (post {post_num}/{POSTS_PER_KEYWORD})\n"
                f"📝 Title: {title}\n\n"
                f"This title already exists. Slot skipped."
            )
            STATS.posts_skipped.append({"keyword": kw, "reason": f"duplicate title (post {post_num})"})
            continue

        # Step 2: Slug
        slug, slug_ok = get_unique_slug(kw)
        if not slug_ok:
            send_telegram(
                f"⏭️ <b>Post Skipped — All Slugs Exist</b>\n\n"
                f"🔑 Keyword: <b>{kw}</b> (post {post_num}/{POSTS_PER_KEYWORD})\n"
                f"🔗 Base Slug: {slug}\n\n"
                f"All slug variations exist. Slot skipped."
            )
            STATS.posts_skipped.append({"keyword": kw, "reason": f"all slugs exist (post {post_num})"})
            continue

        # Step 3: Build content
        focus_kw    = generate_focus_keyword(kw)
        intro       = generate_intro(kw)
        meta_desc   = generate_meta_description(kw)
        subheadings = fetch_subheadings_from_google(kw, count=5)
        category_id = match_category(title, categories)
        cat_name    = next((c["name"] for c in categories if c["id"] == category_id), "Unknown")

        log(f"  Title      : {title}")
        log(f"  Slug       : {slug}")
        log(f"  Focus KW   : {focus_kw}")
        log(f"  Category   : {cat_name}")
        log(f"  Subheadings: {' | '.join(subheadings)}")
        log(f"  Meta Desc  : {meta_desc[:80]}...")

        html_content = build_html_gallery(
            subheadings, all_media, IMAGES_PER_HEADING, kw, intro,
            recent_posts=recent_posts_for_links,
            current_title=title
        )

        if dry_run:
            log(f"  [DRY RUN] Would publish: '{title}' (post {post_num}/{POSTS_PER_KEYWORD})")
            log(f"  [DRY RUN] Slug         : {slug}")
            log(f"  [DRY RUN] Category     : {cat_name} (ID={category_id})")
            log(f"  [DRY RUN] HTML size    : {len(html_content)} chars")

            STATS.posts_created.append({
                "title":        title,
                "link":         f"https://radhakrishnaphoto.in/{slug}/",
                "category":     cat_name,
                "keyword":      kw,
                "post_num":     f"post {post_num}/{POSTS_PER_KEYWORD}",
                "published_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
            })

            kw_lower = kw.lower()
            in_run_published[kw_lower] = in_run_published.get(kw_lower, 0) + 1
            total_done = used_keywords_dict.get(kw_lower, 0) + in_run_published[kw_lower]
            save_keyword_progress(kw, total_done)
            existing_titles.add(title.strip().lower())

        else:
            post_id, post_link = create_wp_post(
                title, slug, html_content, category_id, focus_kw, meta_desc
            )

            if post_id:
                published_at = datetime.now().strftime("%d %b %Y %I:%M %p")
                log(f"  ✓ Published! ID={post_id} | Slug={slug} | {published_at}")
                log(f"  ✓ URL: {post_link}")

                kw_lower = kw.lower()
                in_run_published[kw_lower] = in_run_published.get(kw_lower, 0) + 1
                total_done = used_keywords_dict.get(kw_lower, 0) + in_run_published[kw_lower]
                save_keyword_progress(kw, total_done)
                existing_titles.add(title.strip().lower())

                STATS.posts_created.append({
                    "title":        title,
                    "link":         post_link,
                    "category":     cat_name,
                    "keyword":      kw,
                    "post_num":     f"post {post_num}/{POSTS_PER_KEYWORD}",
                    "published_at": published_at,
                })

            else:
                log(f"  ✗ Failed to create post for '{kw}' (post {post_num}/{POSTS_PER_KEYWORD})")
                STATS.posts_failed.append(f"{kw} (post {post_num})")

        # ── Gap between posts ─────────────────────────────────
        if i < len(selected) - 1 and gap_seconds > 0:
            next_post_time = datetime.now() + timedelta(seconds=gap_seconds)
            log(f"  ⏳ Waiting {gap_human} before next post...")
            log(f"  ⏳ Next post at: {next_post_time.strftime('%d %b %Y %I:%M %p')}")
            time.sleep(gap_seconds)

    # ── Final Summary ─────────────────────────────────────────
    log(f"\n{'='*60}")
    log(f"Done | Created: {len(STATS.posts_created)} | Failed: {len(STATS.posts_failed)} | Skipped: {len(STATS.posts_skipped)}")
    log(f"Total time: {STATS.elapsed()}")
    log(f"{'='*60}\n")

    summary = build_telegram_summary(STATS)
    send_telegram(summary)


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto WordPress Post Creator for RadhaKrishnaPhoto.in v20")
    parser.add_argument("--posts",      type=int,            default=POSTS_PER_RUN, help="Number of posts to create this run")
    parser.add_argument("--dry-run",    action="store_true",                        help="Preview without posting to WordPress")
    parser.add_argument("--skip-sleep", action="store_true",                        help="Skip random startup sleep only")
    args = parser.parse_args()

    run(posts_to_create=args.posts, dry_run=args.dry_run, skip_sleep=args.skip_sleep)
