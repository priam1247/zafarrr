import os
import requests
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY = os.getenv("FOOTBALL_KEY")

def test_facebook():
    print("Testing Facebook connection...")
    url = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
    msg = (
        "🧪 Bot Test Post\n\n"
        "🚩 Live: Arsenal 2-1 Chelsea\n\n"
        "⚽ Goal: Saka (67')\n\n"
        "📺 Premier League | Troy Zafar Football\n\n"
        "(This is a test post — delete after checking)"
    )
    r = requests.post(url, data={"message": msg, "access_token": FB_TOKEN})
    if r.status_code == 200:
        print("✅ Facebook OK — check your page, test post is live!")
    else:
        print(f"❌ Facebook FAILED: {r.status_code}")
        print(r.text)

def test_football_api():
    print("\nTesting football-data.org API connection...")
    headers = {"X-Auth-Token": FOOTBALL_KEY}
    r = requests.get("https://api.football-data.org/v4/competitions/PL", headers=headers)
    if r.status_code == 200:
        print("✅ Football API OK — Premier League data accessible!")
    else:
        print(f"❌ Football API FAILED: {r.status_code}")
        print(r.text)

def test_credentials_loaded():
    print("Checking credentials in .env...\n")
    ok = True
    if not FB_TOKEN or "your_" in FB_TOKEN:
        print("❌ FB_TOKEN not set in .env")
        ok = False
    else:
        print("✅ FB_TOKEN loaded")

    if not FB_PAGE_ID or "your_" in FB_PAGE_ID:
        print("❌ FB_PAGE_ID not set in .env")
        ok = False
    else:
        print("✅ FB_PAGE_ID loaded")

    if not FOOTBALL_KEY or "your_" in FOOTBALL_KEY:
        print("❌ FOOTBALL_KEY not set in .env")
        ok = False
    else:
        print("✅ FOOTBALL_KEY loaded")

    return ok

if __name__ == "__main__":
    print("=" * 40)
    print("  Troy Zafar Football Bot — Test Mode")
    print("=" * 40 + "\n")

    if test_credentials_loaded():
        test_football_api()
        test_facebook()
        print("\n✅ All tests done. If both passed, run: python run.py")
    else:
        print("\n❌ Fix your .env file first then run this again.")
