import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLAUDE_KEY = os.getenv("CLAUDE_KEY")

def test_claude():
    print("Testing Claude API connection...")

    if not CLAUDE_KEY or "your_" in CLAUDE_KEY:
        print("❌ CLAUDE_KEY not set in .env or Railway Variables")
        return

    print("✅ CLAUDE_KEY loaded")

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 100,
                "messages": [{
                    "role": "user",
                    "content": (
                        "Rewrite this football news in 2 simple sentences: "
                        "Salah to leave Liverpool and become free agent"
                    )
                }]
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            result = data["content"][0]["text"].strip()
            print(f"✅ Claude API working!")
            print(f"\nTest rewrite:")
            print(f"---")
            print(result)
            print(f"---")
        else:
            print(f"❌ Claude API failed: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"❌ Claude API error: {e}")

if __name__ == "__main__":
    print("=" * 40)
    print("  Goal Score ZFR — Claude API Test")
    print("=" * 40 + "\n")
    test_claude()
