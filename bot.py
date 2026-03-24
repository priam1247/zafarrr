import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from reel_generator import create_and_post_reel

load_dotenv()

FB_TOKEN     = os.getenv("FB_TOKEN")
FB_PAGE_ID   = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY = os.getenv("FOOTBALL_KEY")

FOOTBALL_BASE = "https://api.football-data.org/v4"
FB_POST_URL   = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
STATE_FILE    = "match_state.json"

LEAGUES = {
    "PL":  "Premier League",
    "PD":  "La Liga",
    "SA":  "Serie A",
    "CL":  "Champions League",
    "BL1": "Bundesliga",
}

LEAGUE_FLAGS = {
    "PL":  "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "PD":  "🇪🇸",
    "SA":  "🇮🇹",
    "CL":  "🏆",
    "BL1": "🇩🇪",
}

# ── Persistent state ─────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return (
                    set(data.get("goals", [])),
                    set(data.get("cards", [])),
                    set(data.get("lineups", [])),
                    set(data.get("halftimes", [])),
                    set(data.get("fulltimes", [])),
                    set(data.get("matchdays", [])),
                )
        except Exception:
            pass
    return set(), set(), set(), set(), set(), set()

def save_state(goals, cards, lineups, halftimes, fulltimes, matchdays):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "goals":     list(goals),
            "cards":     list(cards),
            "lineups":   list(lineups),
            "halftimes": list(halftimes),
            "fulltimes": list(fulltimes),
            "matchdays": list(matchdays),
        }, f)

posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays = load_state()

# ── Helpers ──────────────────────────────────────────────────────
def football_get(path):
    headers = {"X-Auth-Token": FOOTBALL_KEY}
    try:
        r = requests.get(f"{FOOTBALL_BASE}{path}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[ERROR] API request failed: {e}")
    return None

def post_to_facebook(message):
    payload = {"message": message, "access_token": FB_TOKEN}
    r = requests.post(FB_POST_URL, data=payload, timeout=10)
    if r.status_code == 200:
        print(f"[POSTED] {message[:70]}...")
    else:
        print(f"[ERROR] FB post failed: {r.status_code} {r.text}")

def get_score(match):
    home = match["homeTeam"]["shortName"]
    away = match["awayTeam"]["shortName"]
    ft   = match["score"]["fullTime"]
    ht   = match["score"]["halfTime"]
    hs   = ft["home"] if ft["home"] is not None else (ht["home"] or 0)
    as_  = ft["away"] if ft["away"] is not None else (ht["away"] or 0)
    return home, away, hs, as_

# ── Matchday preview ─────────────────────────────────────────────
def handle_matchday_preview(all_matches_today):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"matchday_{today}"
    if key in posted_matchdays:
        return

    if not all_matches_today:
        return

    lines = ["🗓️ MATCH DAY!\n"]
    for league_code, matches in all_matches_today.items():
        league_name = LEAGUES[league_code]
        flag = LEAGUE_FLAGS[league_code]
        lines.append(f"{flag} {league_name}")
        for m in matches:
            home = m["homeTeam"]["shortName"]
            away = m["awayTeam"]["shortName"]
            kickoff_str = m.get("utcDate", "")
            try:
                kickoff = datetime.strptime(kickoff_str, "%Y-%m-%dT%H:%M:%SZ")
                time_str = kickoff.strftime("%H:%M UTC")
            except Exception:
                time_str = "TBD"
            lines.append(f"  ⚔️  {home} vs {away} — {time_str}")
        lines.append("")

    lines.append("Follow Goal Score ZFR for live updates")
    posted_matchdays.add(key)
    save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)
    post_to_facebook("\n".join(lines))

# ── Lineups ──────────────────────────────────────────────────────
def handle_lineups(match, league_name):
    match_id = match["id"]
    key = f"{match_id}_lineup"
    if key in posted_lineups:
        return

    home = match["homeTeam"]["shortName"]
    away = match["awayTeam"]["shortName"]
    lineups = match.get("lineups", [])
    if len(lineups) < 2:
        return

    def format_players(lineup):
        players = lineup.get("startXI", [])
        return "\n".join(
            f"  {i+1}. {p.get('player', {}).get('name', '')}"
            for i, p in enumerate(players)
        )

    posted_lineups.add(key)
    save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)
    msg = (
        f"📋 Lineups: {home} vs {away}\n\n"
        f"🔵 {home}:\n{format_players(lineups[0])}\n\n"
        f"🔴 {away}:\n{format_players(lineups[1])}\n\n"
        f"🏆 {league_name}\n\n"
        f"Follow Goal Score ZFR for live updates"
    )
    post_to_facebook(msg)

# ── Goals ────────────────────────────────────────────────────────
def handle_goals(match, league_name):
    match_id = match["id"]
    home, away, hs, as_ = get_score(match)

    for goal in match.get("goals", []):
        scorer  = goal.get("scorer", {}).get("name", "Unknown")
        assist  = goal.get("assist", {})
        minute  = goal.get("minute", "?")
        team    = goal.get("team", {}).get("shortName", "")
        key     = f"{match_id}_{team}_{minute}_{scorer}"

        if key not in posted_goals:
            posted_goals.add(key)
            save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)

            assist_line = ""
            if assist and assist.get("name"):
                assist_line = f"🅰️ Assist: {assist['name']}\n\n"

            msg = (
                f"🚩 Live: {home} {hs}-{as_} {away}\n\n"
                f"⚽ Goal: {scorer} ({minute}')\n"
                f"{assist_line}"
                f"🏆 {league_name}\n\n"
                f"Follow Goal Score ZFR for updates"
            )
            post_to_facebook(msg)

# ── Red cards ────────────────────────────────────────────────────
def handle_red_cards(match, league_name):
    match_id = match["id"]
    home, away, hs, as_ = get_score(match)

    for booking in match.get("bookings", []):
        if booking.get("card") == "RED_CARD":
            player = booking.get("player", {}).get("name", "Unknown")
            minute = booking.get("minute", "?")
            team   = booking.get("team", {}).get("shortName", "")
            key    = f"{match_id}_{player}_{minute}"

            if key not in posted_cards:
                posted_cards.add(key)
                save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)
                msg = (
                    f"🚩 Live: {home} {hs}-{as_} {away}\n\n"
                    f"🟥 Red Card: {player} ({minute}') — {team}\n\n"
                    f"🏆 {league_name}\n\n"
                    f"Follow Goal Score ZFR for updates"
                )
                post_to_facebook(msg)

# ── Half time ────────────────────────────────────────────────────
def handle_halftime(match, league_name):
    match_id = match["id"]
    key = f"{match_id}_halftime"
    if key in posted_halftimes:
        return

    home = match["homeTeam"]["shortName"]
    away = match["awayTeam"]["shortName"]
    hs   = match["score"]["halfTime"]["home"] or 0
    as_  = match["score"]["halfTime"]["away"] or 0

    goals = match.get("goals", [])
    goal_lines = []
    for g in goals:
        scorer = g.get("scorer", {}).get("name", "Unknown")
        minute = g.get("minute", "?")
        team   = g.get("team", {}).get("shortName", "")
        goal_lines.append(f"  ⚽ {scorer} ({minute}') — {team}")

    goals_summary = "\n".join(goal_lines) if goal_lines else "  No goals yet"

    posted_halftimes.add(key)
    save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)
    msg = (
        f"⏸️ Half Time: {home} {hs}-{as_} {away}\n\n"
        f"Goals:\n{goals_summary}\n\n"
        f"🏆 {league_name}\n\n"
        f"Follow Goal Score ZFR for updates"
    )
    post_to_facebook(msg)

# ── Full time ────────────────────────────────────────────────────
def handle_fulltime(match, league_name):
    match_id = match["id"]
    key = f"{match_id}_fulltime"
    if key in posted_ft:
        return

    home, away, hs, as_ = get_score(match)

    goals = match.get("goals", [])
    goal_lines = []
    for g in goals:
        scorer = g.get("scorer", {}).get("name", "Unknown")
        assist = g.get("assist", {})
        minute = g.get("minute", "?")
        team   = g.get("team", {}).get("shortName", "")
        assist_str = f" (assist: {assist['name']})" if assist and assist.get("name") else ""
        goal_lines.append(f"  ⚽ {scorer}{assist_str} ({minute}') — {team}")

    goals_summary = "\n".join(goal_lines) if goal_lines else "  No goals"

    if hs > as_:
        result = f"{home} win!"
    elif as_ > hs:
        result = f"{away} win!"
    else:
        result = "It's a draw!"

    posted_ft.add(key)
    save_state(posted_goals, posted_cards, posted_lineups, posted_halftimes, posted_ft, posted_matchdays)
    msg = (
        f"🏁 Full Time: {home} {hs}-{as_} {away}\n\n"
        f"{result}\n\n"
        f"Goals:\n{goals_summary}\n\n"
        f"🏆 {league_name}\n\n"
        f"Follow Goal Score ZFR for updates"
    )
    post_to_facebook(msg)

    # Generate and post reel after full time
    create_and_post_reel(match, league_name)

# ── Main loop ────────────────────────────────────────────────────
matchday_posted_today = None

def check_matches():
    global matchday_posted_today
    today = datetime.utcnow().strftime("%Y-%m-%d")

    all_matches_today = {}
    for code in LEAGUES:
        data = football_get(f"/competitions/{code}/matches?dateFrom={today}&dateTo={today}")
        if data:
            matches = data.get("matches", [])
            if matches:
                all_matches_today[code] = matches

    # Post matchday preview once per day if there are games
    if matchday_posted_today != today:
        handle_matchday_preview(all_matches_today)
        matchday_posted_today = today

    # Process each match
    for code, matches in all_matches_today.items():
        league_name = LEAGUES[code]
        for match in matches:
            status = match.get("status")

            # Lineups — 45 to 75 mins before kickoff
            if status in ("TIMED", "SCHEDULED"):
                kickoff_str = match.get("utcDate", "")
                if kickoff_str:
                    kickoff = datetime.strptime(kickoff_str, "%Y-%m-%dT%H:%M:%SZ")
                    now = datetime.utcnow()
                    if timedelta(minutes=45) <= kickoff - now <= timedelta(minutes=75):
                        handle_lineups(match, league_name)

            # Live events
            if status == "IN_PLAY":
                handle_goals(match, league_name)
                handle_red_cards(match, league_name)

            # Half time
            if status == "PAUSED":
                handle_halftime(match, league_name)

            # Full time
            if status == "FINISHED":
                handle_fulltime(match, league_name)

def run():
    print("Goal Score ZFR Match Bot started...")
    print(f"Monitoring: {', '.join(LEAGUES.values())}")
    print("Posting: Matchday preview, Lineups, Goals + Assists, Red Cards, Half Time, Full Time\n")

    while True:
        try:
            check_matches()
        except Exception as e:
            print(f"[ERROR] {e}")
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checked. Waiting 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    run()
