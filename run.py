import os
import threading
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler

load_dotenv()

import bot
import news_bot

# ── Tiny web server to keep Railway alive ────────────────────────
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Goal Score ZFR Bot is running!")

    def log_message(self, format, *args):
        pass  # Silence HTTP logs so terminal stays clean

def run_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()

# ── Start everything ─────────────────────────────────────────────
print("=" * 40)
print("  Troy Zafar Football Bot — Full Suite")
print("=" * 40)
print()
print("Starting match bot + news bot simultaneously...")
print()

# Web server thread — keeps Railway alive
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
print(f"Keep-alive server started on port {os.getenv('PORT', 8080)}")

# Match bot thread
match_thread = threading.Thread(target=bot.run, daemon=True)
match_thread.start()

# News bot thread
news_thread = threading.Thread(target=news_bot.run, daemon=True)
news_thread.start()

# Keep the program alive
match_thread.join()
news_thread.join()
