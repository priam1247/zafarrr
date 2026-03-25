import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN      = os.getenv("FB_TOKEN")
FB_PAGE_ID    = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY  = os.getenv("FOOTBALL_KEY")
CLAUDE_KEY    = os.getenv("CLAUDE_KEY")

FB_POST_URL    = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
FOOTBALL_BASE  = "https://api.football-data.org/v4"
NEWS_STATE_FILE = "news_state.json"

# ── All leagues for matchday detection ───────────────────────────
ALL_LEAGUES = [
    "PL","PD","SA","CL","BL1","FL1","DED","ELC","PPL","BSA","WC","EC"
]

# ── 2 trusted sources only ────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Goal.com",   "url": "https://www.goal.com/en/feeds/news?fmt=rss"},
    {"name": "Sky Sports", "url": "https://www.skysports.com/rss/0,20514,11095,00.xml"},
]

# ── Category detection ────────────────────────────────────────────
CATEGORIES = {
    "BREAKING": {
        "emoji": "🚨",
        "keywords": ["breaking", "just in", "urgent", "alert"],
        "priority": True
    },
    "TRANSFER": {
        "emoji": "🔴",
        "keywords": ["transfer", "signing", "signs", "sign", "move", "deal", "fee",
                     "loan", "free agent", "bid", "offer", "target", "want",
                     "interested", "approach", "agree", "done deal", "medical"],
        "priority": False
    },
    "INJURY": {
        "emoji": "🤕",
        "keywords": ["injury", "injured", "out for", "miss", "scan", "fitness",
                     "doubt", "ruled out", "surgery", "fracture", "muscle"],
        "priority": False
    },
    "CONTRACT": {
        "emoji": "📝",
        "keywords": ["contract", "extends", "extension", "renew", "renewal",
                     "new deal", "signs new", "until 20"],
        "priority": False
    },
    "SACKED": {
        "emoji": "🔫",
        "keywords": ["sacked", "fired", "dismissed", "leaves", "parts ways",
                     "relieved of", "resign", "resignation"],
        "priority": False
    },
    "OFFICIAL": {
        "emoji": "✅",
        "keywords": ["official", "confirmed", "announced", "unveil", "unveiled",
                     "completed", "done", "sealed"],
        "priority": True
    },
    "BANNED": {
        "emoji": "🚫",
        "keywords": ["banned", "suspended", "suspension", "ban", "sanction",
                     "disciplinary", "red card appeal"],
        "priority": False
    },
    "APPOINTED": {
        "emoji": "👔",
        "keywords": ["appointed", "new manager", "new coach", "takes charge",
                     "named as", "hired"],
        "priority": False
    },
}

# Quality keywords — only post real news not opinions/filler
QUALITY_KEYWORDS = [
    "transfer", "sign", "injury", "contract", "sack", "appoint", "ban",
    "suspend", "confirm", "official", "breaking", "deal", "free agent",
    "loan", "fee", "bid", "offer", "agree", "done", "medical", "unveil",
    "leave", "join", "depart", "arrive", "manager", "coach", "squad",
    "premier league", "la liga", "serie a", "bundesliga", "champions league",
    "ligue 1", "eredivisie", "world cup", "euro",
    "barcelona", "real madrid", "manchester", "liverpool", "arsenal",
    "chelsea", "juventus", "milan", "inter", "bayern", "dortmund",
    "psg", "atletico", "tottenham", "newcastle", "city", "united"
]

# Filler to skip — low quality content
FILLER_KEYWORDS = [
    "5 things", "player ratings", "fan reaction", "remember when",
    "best goals", "worst goals", "quiz", "ranked", "every goal",
    "watch:", "video:", "gallery:", "photos:", "in pictures"
]

# Football entity names for deduplication
PLAYER_NAMES = [
    "salah", "haaland", "mbappe", "vinicius", "bellingham", "saka",
    "odegaard", "de bruyne", "kane", "lewandowski", "messi", "ronaldo",
    "neymar", "rashford", "fernandes", "rice", "rodri", "pedri",
    "yamal", "gavi", "ter stegen", "alisson", "ederson", "courtois"
]

CLUB_NAMES = [
    "liverpool", "manchester city", "manchester united", "arsenal", "chelsea",
    "tottenham", "newcastle", "barcelona", "real madrid", "atletico",
    "juventus", "milan", "inter", "napoli", "bayern", "dortmund",
    "psg", "ajax", "porto", "benfica", "celtic", "rangers"
]

# ── Persistent state ──────────────────────────────────────────────
def load_news_state():
    if os.path.exists(NEWS_STATE_FILE):
        try:
            with open(NEWS_STATE_FILE, "r") as f:
                data = json.load(f)
                return (
                    set(data.get("posted_keys", [])),
                    data.get("last_post_time", 0),
                    data.get("posts_today", 0),
                    data.get("last_reset_date", ""),
                    list(data.get("recent_entities", [])),
                    data.get("last_source", ""),
                )
        except Exception:
            pass
    return set(), 0, 0, "", [], ""

def save_news_state(posted_keys, last_post_time, posts_today,
                    last_reset_date, recent_entities, last_source):
    with open(NEWS_STATE_FILE, "w") as f:
        json.dump({
            "posted_keys":     list(posted_keys),
            "last_post_time":  last_post_time,
            "posts_today":     posts_today,
            "last_reset_date": last_reset_date,
            "recent_entities": list(recent_entities)[-100:],
            "last_source":     last_source,
        }, f)

(posted_keys, last_post_time,
 posts_today, last_reset_date,
 recent_entities, last_source) = load_news_state()

# ── Helpers ───────────────────────────────────────────────────────
def clean_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9 ]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title

def detect_category(title, desc=""):
    text = (title + " " + desc).lower()
    for cat_name, cat_data in CATEGORIES.items():
        if any(kw in text for kw in cat_data["keywords"]):
            return cat_name, cat_data["emoji"], cat_data["priority"]
    return "NEWS", "📰", False

def is_quality_story(title, desc=""):
    text = (title + " " + desc).lower()
    if any(filler in text for filler in FILLER_KEYWORDS):
        return False
    return any(kw in text for kw in QUALITY_KEYWORDS)

def extract_entities(title):
    text = title.lower()
    found = []
    for name in PLAYER_NAMES + CLUB_NAMES:
        if name in text:
            found.append(name)
    return found

def is_duplicate_entity(title):
    """Block same player/club combo posted in last 4 hours."""
    entities = extract_entities(title)
    now = time.time()
    for entry in recent_entities:
        entry_time  = entry.get("time", 0)
        entry_names = entry.get("entities", [])
        if now - entry_time < 14400:  # 4 hours
            overlap = set(entities) & set(entry_names)
            if len(overlap) >= 1 and len(entities) > 0:
                return True
    return False

def add_entity_record(title):
    entities = extract_entities(title)
    if entities:
        recent_entities.append({"time": time.time(), "entities": entities})

def is_matchday():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for code in ALL_LEAGUES:
        try:
            headers = {"X-Auth-Token": FOOTBALL_KEY}
            r = requests.get(
                f"{FOOTBALL_BASE}/competitions/{code}/matches"
                f"?dateFrom={today}&dateTo={today}",
                headers=headers, timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("matches"):
                    return True
        except Exception:
            pass
    return False

def fetch_rss(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"[ERROR] RSS fetch failed: {e}")
    return None

# ── Claude AI rewriter ────────────────────────────────────────────
def rewrite_with_claude(title, description, category):
    if not CLAUDE_KEY:
        return None
    try:
        prompt = (
            f"You are a football news writer for a Facebook page called Goal Score ZFR.\n"
            f"Rewrite this football news in very simple English that anyone in the world can understand.\n"
            f"Maximum 3 short sentences. No complex words. Be direct and clear.\n"
            f"Do not include any hashtags, links or emojis.\n"
            f"Do not start with the category name.\n\n"
            f"News headline: {title}\n"
            f"Details: {description[:300] if description else 'No details'}\n\n"
            f"Rewritten (3 sentences max):"
        )
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[ERROR] Claude rewrite failed: {e}")
    return None

def post_to_facebook(message):
    payload = {"message": message, "access_token": FB_TOKEN}
    r = requests.post(FB_POST_URL, data=payload, timeout=10)
    if r.status_code == 200:
        print(f"[POSTED] {message[:80]}...")
        return True
    else:
        print(f"[ERROR] FB post failed: {r.status_code} {r.text}")
        return False

def format_post(category, emoji, rewritten, original_title, source):
    label = f"{emoji} {category} |"
    text  = rewritten if rewritten else original_title
    return (
        f"{label} {text}\n\n"
        f"📡 Source: {source}\n\n"
        f"Follow Goal Score ZFR for updates"
    )

# ── Main news checker ─────────────────────────────────────────────
def check_news():
    global last_post_time, posts_today, last_reset_date, last_source

    # Reset daily counter at midnight UTC
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        print(f"[NEWS] Daily counter reset. New day: {today_str}")

    # Max 30 posts per day
    if posts_today >= 30:
        print(f"[NEWS] Daily limit reached ({posts_today}/30). Waiting for tomorrow.")
        return

    # Determine posting gap based on matchday
    matchday = is_matchday()
    gap = 7200 if matchday else 2700  # 2 hours on matchday, 45 mins otherwise
    gap_label = "2 hours (matchday)" if matchday else "45 mins (no games)"

    now_ts = time.time()
    elapsed = now_ts - last_post_time
    remaining = int((gap - elapsed) / 60)

    if elapsed < gap:
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
              f"Next news in {remaining} mins ({gap_label})")
        return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking news feeds...")

    # Source rotation — alternate between Goal.com and Sky Sports
    feeds_ordered = RSS_FEEDS.copy()
    if last_source == RSS_FEEDS[0]["name"]:
        feeds_ordered = [RSS_FEEDS[1], RSS_FEEDS[0]]

    for feed in feeds_ordered:
        tree = fetch_rss(feed["url"])
        if tree is None:
            continue

        items = (tree.findall(".//item") or
                 tree.findall(".//{http://www.w3.org/2005/Atom}entry"))

        for item in items[:8]:
            # Get title
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue

            # Get description
            desc_el = item.find("description")
            desc = (desc_el.text or "") if desc_el is not None else ""
            # Strip HTML tags from description
            desc = re.sub(r'<[^>]+>', '', desc).strip()

            # Quality check — skip filler
            if not is_quality_story(title, desc):
                continue

            # Exact duplicate check
            key = clean_title(title)
            if key in posted_keys:
                continue

            # Entity duplicate check — same player/club within 4 hours
            if is_duplicate_entity(title):
                print(f"[SKIP] Duplicate entity: {title[:50]}")
                posted_keys.add(key)
                continue

            # Detect category
            category, emoji, is_priority = detect_category(title, desc)

            # Breaking/Official news skips the time gap
            if not is_priority and elapsed < gap:
                continue

            # Rewrite with Claude AI
            rewritten = rewrite_with_claude(title, desc, category)

            # Format and post
            msg = format_post(category, emoji, rewritten, title, feed["name"])
            success = post_to_facebook(msg)

            if success:
                posted_keys.add(key)
                add_entity_record(title)
                last_post_time = time.time()
                last_source = feed["name"]
                posts_today += 1
                save_news_state(posted_keys, last_post_time, posts_today,
                                last_reset_date, recent_entities, last_source)
                print(f"[NEWS] Posted ({posts_today}/30 today). "
                      f"Category: {category}. Source: {feed['name']}")
                return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No new quality stories found.")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print("Goal Score ZFR News Bot started...")
    print("Sources: Goal.com (alternating) Sky Sports")
    print("AI rewriter: Claude API")
    print("Smart matchday detection: ON")
    print("Duplicate filter: ON\n")

    while True:
        try:
            check_news()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(900)  # Check every 15 minutes

if __name__ == "__main__":
    run()
