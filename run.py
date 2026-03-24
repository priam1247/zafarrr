import os
import threading
from dotenv import load_dotenv

load_dotenv()

import bot
import news_bot

print("=" * 40)
print("  Troy Zafar Football Bot — Full Suite")
print("=" * 40)
print()
print("Starting match bot + news bot simultaneously...")
print()

# Run match bot in one thread
match_thread = threading.Thread(target=bot.run, daemon=True)
match_thread.start()

# Run news bot in another thread
news_thread = threading.Thread(target=news_bot.run, daemon=True)
news_thread.start()

# Keep the program alive
match_thread.join()
news_thread.join()
