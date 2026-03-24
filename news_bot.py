import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN    = os.getenv("FB_TOKEN")
FB_PAGE_ID  = os.getenv("FB_PAGE_ID")
FB_POST_URL = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
NEWS_STATE_FILE = "news_state.json"

# ── 2 trusted sources only ────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Goal.com",   "url": "https://www.goal.com/en/feeds/news?fmt=rss"},
    {"name": "Sky Sports", "url": "https://www.skysports.com/rss/0,20514,11095,00.xml"},
]

KEYWORDS = [
    "transfer", "signing", "injury", "suspended", "banned",
    "sacked", "appointed", "contract", "premier league", "la liga",
    "serie a", "bundesliga", "champions league", "ligue 1",
    "goal", "match", "manager", "coach", "squad", "lineup",
    "breaking", "official", "confirmed", "deal", "loan",
    "barcelona", "real madrid", "manchester", "liverpool", "arsenal",
    "chelsea", "juventus", "milan", "inter", "bayern", "dortmund",
    "psg", "atletico", "tottenham", "newcastle", "city", "united"
]

# ── Persistent state ─────────────────────────────────────────────
def load_news_state():
    if os.path.exists(NEWS_STATE_FILE):
        try:
            with open(NEWS_STATE_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("posted", [])), data.get("last_post_time", 0)
        except Exception:
            pass
    return set(), 0

def save_news_state(posted, last_post_time):
    with open(NEWS_STATE_FILE, "w") as f:
        json.dump({"posted": list(posted), "last_post_time": last_post_time}, f)

posted_titles, last_post_time = load_news_state()

# ── Helpers ──────────────────────────────────────────────────────
def clean_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9 ]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title

def fetch_rss(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"[ERROR] RSS fetch failed for {url}: {e}")
    return None

def is_football_relevant(title, description=""):
    text = (title + " " + description).lower()
    return any(kw in text for kw in KEYWORDS)

def format_news_post(title, source):
    return (
        f"📰 {title}\n\n"
        f"📡 Source: {source}\n\n"
        f"Follow Goal Score ZFR for updates"
    )

def post_to_facebook(message):
    payload = {"message": message, "access_token": FB_TOKEN}
    r = requests.post(FB_POST_URL, data=payload, timeout=10)
    if r.status_code == 200:
        print(f"[POSTED] {message[:60]}...")
    else:
        print(f"[ERROR] FB post failed: {r.status_code} {r.text}")

# ── Main news checker ─────────────────────────────────────────────
def check_news():
    global last_post_time
    now_ts = time.time()

    # Enforce 2 hour minimum gap between any news post
    if now_ts - last_post_time < 7200:
        remaining = int((7200 - (now_ts - last_post_time)) / 60)
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Waiting {remaining} mins before next news post.")
        return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking news feeds...")

    for feed in RSS_FEEDS:
        tree = fetch_rss(feed["url"])
        if tree is None:
            continue

        items = tree.findall(".//item") or tree.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items[:5]:
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue

            key = clean_title(title)
            if key in posted_titles:
                continue

            desc_el = item.find("description")
            desc = (desc_el.text or "") if desc_el is not None else ""

            if not is_football_relevant(title, desc):
                continue

            # Post the story
            posted_titles.add(key)
            last_post_time = time.time()
            save_news_state(posted_titles, last_post_time)

            msg = format_news_post(title, feed["name"])
            post_to_facebook(msg)

            # Found one story — stop and wait 2 hours before next
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Story posted. Next news in 2 hours.")
            return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No new stories found.")

def run():
    print("Goal Score ZFR News Bot started...")
    print("Sources: Goal.com, Sky Sports")
    print("One post every 2 hours minimum\n")

    while True:
        try:
            check_news()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(1800)

if __name__ == "__main__":
    run()
