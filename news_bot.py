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

# Quality keywords — only post real news not opinions
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

# Filler to skip
FILLER_KEYWORDS = [
    "5 things", "player ratings", "fan reaction", "remember when",
    "best goals", "worst goals", "quiz", "ranked", "every goal",
    "watch:", "video:", "gallery:", "photos:", "in pictures",
    "predicted", "how to watch", "tv channel", "live stream",
    "preview:", "vs:", "betting odds"
]

# Entity names for deduplication
PLAYER_NAMES = [
    "salah", "haaland", "mbappe", "vinicius", "bellingham", "saka",
    "odegaard", "de bruyne", "kane", "lewandowski", "messi", "ronaldo",
    "neymar", "rashford", "fernandes", "rice", "rodri", "pedri",
    "yamal", "gavi", "ter stegen", "alisson", "ederson", "courtois",
    "modric", "kroos", "benzema", "griezmann", "dembele", "camavinga"
]

CLUB_NAMES = [
    "liverpool", "manchester city", "manchester united", "arsenal", "chelsea",
    "tottenham", "newcastle", "barcelona", "real madrid", "atletico",
    "juventus", "milan", "inter", "napoli", "bayern", "dortmund",
    "psg", "ajax", "porto", "benfica", "celtic", "rangers", "lazio", "roma"
]

# ── Free template rewriter ────────────────────────────────────────
# Journalist phrases to clean up
CLEAN_PHRASES = [
    (r"'[^']*'\s*[-–—:]\s*", ""),           # Remove 'quote' - at start
    (r'"[^"]*"\s*[-–—:]\s*', ""),           # Remove "quote" - at start
    (r"\baccording to reports\b", ""),
    (r"\bit has been claimed that\b", ""),
    (r"\bit is understood that\b", ""),
    (r"\bit is believed that\b", ""),
    (r"\bsources have told\b.*", ""),
    (r"\bexclusive:\s*", ""),
    (r"\bbreaking:\s*", ""),
    (r"\breport:\s*", ""),
    (r"\breports:\s*", ""),
    (r"\bwatch:\s*", ""),
    (r"\banalysis:\s*", ""),
    (r"\[\d+\]", ""),                        # Remove footnote numbers
    (r"\s{2,}", " "),                        # Clean double spaces
]

# Simple word replacements for plain English
WORD_REPLACEMENTS = [
    ("depart", "leave"),
    ("terminate", "end"),
    ("contractual agreement", "contract"),
    ("upon expiration of", "when his contract ends at"),
    ("set to", "will"),
    ("ahead of", "better than"),
    ("amid", "during"),
    ("following", "after"),
    ("securing", "getting"),
    ("obtaining", "getting"),
    ("potential", "possible"),
    ("currently", "now"),
    ("subsequently", "then"),
    ("previously", "before"),
    ("approximately", "about"),
    ("remainder of", "rest of"),
    ("football club", ""),
    ("fc ", ""),
]

def simplify_title(title):
    """Clean journalist language and simplify to plain English."""
    text = title.strip()

    # Apply regex cleanups
    for pattern, replacement in CLEAN_PHRASES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Apply word replacements
    for old, new in WORD_REPLACEMENTS:
        text = re.sub(r'\b' + re.escape(old) + r'\b', new, text,
                      flags=re.IGNORECASE)

    # Capitalize first letter
    text = text.strip().capitalize()
    return text

def build_simple_sentence(title, desc, category):
    """Build a simple 1-3 sentence explanation from title and description."""
    clean = simplify_title(title)
    text = clean

    # Add context from description if available
    if desc:
        desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
        desc_clean = re.sub(r'\s+', ' ', desc_clean)
        # Only use first sentence of description
        first_sentence = desc_clean.split('.')[0].strip()
        if first_sentence and len(first_sentence) > 20 and first_sentence.lower() not in clean.lower():
            # Simplify the description sentence too
            for old, new in WORD_REPLACEMENTS:
                first_sentence = re.sub(r'\b' + re.escape(old) + r'\b',
                                        new, first_sentence, flags=re.IGNORECASE)
            if len(text) + len(first_sentence) < 280:
                text = f"{clean}. {first_sentence.capitalize()}"

    # Ensure ends with period
    if text and not text.endswith('.'):
        text += '.'

    return text

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
    return [name for name in PLAYER_NAMES + CLUB_NAMES if name in text]

def is_duplicate_entity(title):
    entities = extract_entities(title)
    now = time.time()
    for entry in recent_entities:
        if now - entry.get("time", 0) < 14400:
            overlap = set(entities) & set(entry.get("entities", []))
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
            if r.status_code == 200 and r.json().get("matches"):
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

def post_to_facebook(message):
    payload = {"message": message, "access_token": FB_TOKEN}
    r = requests.post(FB_POST_URL, data=payload, timeout=10)
    if r.status_code == 200:
        print(f"[POSTED] {message[:80]}...")
        return True
    print(f"[ERROR] FB post failed: {r.status_code} {r.text}")
    return False

def format_post(category, emoji, body, source):
    return (
        f"{emoji} {category} | {body}\n\n"
        f"📡 Source: {source}\n\n"
        f"Follow Goal Score ZFR for updates"
    )

# ── Main news checker ─────────────────────────────────────────────
def check_news():
    global last_post_time, posts_today, last_reset_date, last_source

    # Reset daily counter
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        print(f"[NEWS] Daily counter reset.")

    # Max 30 posts per day
    if posts_today >= 30:
        print(f"[NEWS] Daily limit reached (30/30).")
        return

    # Auto detect matchday and set gap
    matchday    = is_matchday()
    gap         = 7200 if matchday else 2700
    gap_label   = "2 hrs (matchday)" if matchday else "45 mins (no games)"
    now_ts      = time.time()
    elapsed     = now_ts - last_post_time
    remaining   = int((gap - elapsed) / 60)

    if elapsed < gap:
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
              f"Next news in {remaining} mins ({gap_label})")
        return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking news feeds...")

    # Source rotation
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
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue

            desc_el = item.find("description")
            desc = re.sub(r'<[^>]+>', '',
                          (desc_el.text or "") if desc_el is not None else "").strip()

            # Quality check
            if not is_quality_story(title, desc):
                continue

            # Exact duplicate check
            key = clean_title(title)
            if key in posted_keys:
                continue

            # Entity duplicate check
            if is_duplicate_entity(title):
                print(f"[SKIP] Same story: {title[:50]}")
                posted_keys.add(key)
                continue

            # Detect category
            category, emoji, is_priority = detect_category(title, desc)

            # Breaking/Official skips the time gap
            if not is_priority and elapsed < gap:
                continue

            # Free template rewrite — simple English
            body = build_simple_sentence(title, desc, category)

            # Format and post
            msg = format_post(category, emoji, body, feed["name"])
            success = post_to_facebook(msg)

            if success:
                posted_keys.add(key)
                add_entity_record(title)
                last_post_time = time.time()
                last_source = feed["name"]
                posts_today += 1
                save_news_state(posted_keys, last_post_time, posts_today,
                                last_reset_date, recent_entities, last_source)
                print(f"[NEWS] Posted ({posts_today}/30). "
                      f"Category: {category}. Source: {feed['name']}")
                return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No new quality stories.")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print("Goal Score ZFR News Bot started...")
    print("Sources: Goal.com / Sky Sports (alternating)")
    print("Rewriter: Free template engine")
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
