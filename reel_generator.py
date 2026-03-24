import os
import time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")

# ── Canvas settings ──────────────────────────────────────────────
WIDTH, HEIGHT = 1080, 1920  # 9:16 vertical reel format
FPS = 30
DURATION_PER_GOAL = 2.5     # seconds per goal reveal
INTRO_DURATION    = 2.0     # seconds for team names intro
OUTRO_DURATION    = 3.0     # seconds for final scoreline

# ── Colors ───────────────────────────────────────────────────────
BG_COLOR       = (15, 15, 25)       # dark navy background
ACCENT_COLOR   = (0, 200, 100)      # green accent
WHITE          = (255, 255, 255)
LIGHT_GRAY     = (180, 180, 180)
GOLD           = (255, 200, 50)
RED_COLOR      = (220, 50, 50)
OVERLAY_COLOR  = (0, 0, 0, 160)     # semi transparent black


def get_font(size, bold=False):
    """Try to load a font, fallback to default if not available."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_background(draw, width, height):
    """Draw dark gradient-style background with decorative elements."""
    draw.rectangle([0, 0, width, height], fill=BG_COLOR)
    # Top accent bar
    draw.rectangle([0, 0, width, 8], fill=ACCENT_COLOR)
    # Bottom accent bar
    draw.rectangle([0, height - 8, width, height], fill=ACCENT_COLOR)
    # Center divider line
    draw.rectangle([width // 2 - 1, height // 4, width // 2 + 1, height * 3 // 4],
                   fill=(255, 255, 255, 30))


def draw_branding(draw, width, height):
    """Draw Goal Score ZFR branding at top and bottom."""
    font_brand = get_font(42, bold=True)
    font_small = get_font(28)

    # Top branding
    brand_text = "GOAL SCORE ZFR"
    bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    bw = bbox[2] - bbox[0]
    draw.text(((width - bw) // 2, 30), brand_text, font=font_brand, fill=ACCENT_COLOR)

    # Bottom follow text
    follow_text = "Follow Goal Score ZFR for live updates"
    bbox2 = draw.textbbox((0, 0), follow_text, font=font_small)
    fw = bbox2[2] - bbox2[0]
    draw.text(((width - fw) // 2, height - 60), follow_text,
              font=font_small, fill=LIGHT_GRAY)


def draw_league_badge(draw, league_name, width, y):
    """Draw league name badge."""
    font = get_font(34, bold=True)
    bbox = draw.textbbox((0, 0), league_name, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = 20
    rx = (width - tw - pad * 2) // 2
    draw.rounded_rectangle([rx, y, rx + tw + pad * 2, y + th + pad],
                            radius=8, fill=(30, 30, 50), outline=ACCENT_COLOR, width=1)
    draw.text((rx + pad, y + pad // 2), league_name, font=font, fill=GOLD)
    return y + th + pad + 20


def make_frame(home, away, home_score, away_score, goals, league_name,
               highlight_goal_index=None, is_final=False):
    """Generate a single frame image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw_background(draw, WIDTH, HEIGHT)
    draw_branding(draw, WIDTH, HEIGHT)

    # League badge
    y = draw_league_badge(draw, league_name, WIDTH, 100)
    y += 20

    # Team names
    font_team = get_font(72, bold=True)
    font_vs    = get_font(40)
    font_score = get_font(160, bold=True)
    font_goal  = get_font(36)
    font_assist = get_font(30)
    font_ft    = get_font(44, bold=True)

    # Home team
    bbox = draw.textbbox((0, 0), home, font=font_team)
    hw = bbox[2] - bbox[0]
    draw.text(((WIDTH // 2 - hw) // 2, y), home, font=font_team, fill=WHITE)

    # Away team
    bbox = draw.textbbox((0, 0), away, font=font_team)
    aw = bbox[2] - bbox[0]
    draw.text((WIDTH // 2 + (WIDTH // 2 - aw) // 2, y), away,
              font=font_team, fill=WHITE)

    y += 100

    # Score
    score_text = f"{home_score}  -  {away_score}"
    bbox = draw.textbbox((0, 0), score_text, font=font_score)
    sw = bbox[2] - bbox[0]
    draw.text(((WIDTH - sw) // 2, y), score_text, font=font_score, fill=WHITE)

    y += 200

    # Divider
    draw.rectangle([80, y, WIDTH - 80, y + 2], fill=ACCENT_COLOR)
    y += 30

    # Goals list
    for i, goal in enumerate(goals):
        scorer  = goal.get("scorer", {}).get("name", "Unknown")
        assist  = goal.get("assist", {})
        minute  = goal.get("minute", "?")
        team    = goal.get("team", {}).get("shortName", "")

        # Highlight current goal being revealed
        if highlight_goal_index is not None and i == highlight_goal_index:
            draw.rounded_rectangle([60, y - 8, WIDTH - 60, y + 80],
                                    radius=8, fill=(0, 180, 80, 80))
            color = WHITE
        elif highlight_goal_index is not None and i > highlight_goal_index:
            color = (60, 60, 80)  # hidden future goals
        else:
            color = LIGHT_GRAY

        goal_line = f"⚽  {scorer}  ({minute}')  —  {team}"
        draw.text((80, y), goal_line, font=font_goal, fill=color)
        y += 44

        if assist and assist.get("name") and (
                highlight_goal_index is None or i <= highlight_goal_index):
            assist_line = f"     🅰  Assist: {assist['name']}"
            draw.text((80, y), assist_line, font=font_assist, fill=ACCENT_COLOR)
            y += 36

        y += 10

    y += 20

    # Full time banner
    if is_final:
        draw.rectangle([80, y, WIDTH - 80, y + 70], fill=ACCENT_COLOR)
        ft_text = "FULL TIME"
        bbox = draw.textbbox((0, 0), ft_text, font=font_ft)
        fw = bbox[2] - bbox[0]
        draw.text(((WIDTH - fw) // 2, y + 12), ft_text, font=font_ft, fill=BG_COLOR)

    return np.array(img)


def generate_reel(home, away, home_score, away_score, goals, league_name, output_path):
    """Generate full animated reel video."""
    clips = []

    # Intro frame — teams and 0-0
    intro_frame = make_frame(home, away, 0, 0, [], league_name)
    clips.append(ImageClip(intro_frame).set_duration(INTRO_DURATION))

    # Reveal goals one by one
    hs, as_ = 0, 0
    for i, goal in enumerate(goals):
        team = goal.get("team", {}).get("shortName", "")
        if team == home:
            hs += 1
        else:
            as_ += 1

        frame = make_frame(home, away, hs, as_, goals[:i+1],
                           league_name, highlight_goal_index=i)
        clips.append(ImageClip(frame).set_duration(DURATION_PER_GOAL))

    # Final scoreline frame
    final_frame = make_frame(home, away, home_score, away_score,
                             goals, league_name, is_final=True)
    clips.append(ImageClip(final_frame).set_duration(OUTRO_DURATION))

    # Concatenate all clips
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio=False, verbose=False, logger=None)
    print(f"[REEL] Generated: {output_path}")
    return output_path


def post_reel_to_facebook(video_path, caption):
    """Upload reel video to Facebook page."""
    print(f"[REEL] Uploading to Facebook...")

    # Step 1 — Initialize upload
    init_url = f"https://graph.facebook.com/{FB_PAGE_ID}/video_reels"
    init_payload = {
        "upload_phase": "start",
        "access_token": FB_TOKEN
    }
    r = requests.post(init_url, data=init_payload, timeout=30)
    if r.status_code != 200:
        print(f"[ERROR] Reel init failed: {r.status_code} {r.text}")
        return
    upload_data = r.json()
    video_id    = upload_data.get("video_id")
    upload_url  = upload_data.get("upload_url")

    if not video_id or not upload_url:
        print(f"[ERROR] No video_id or upload_url returned: {upload_data}")
        return

    # Step 2 — Upload the video file
    file_size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        upload_headers = {
            "Authorization": f"OAuth {FB_TOKEN}",
            "offset":        "0",
            "file_size":     str(file_size),
        }
        ur = requests.post(upload_url, headers=upload_headers,
                           data=f, timeout=120)
    if ur.status_code != 200:
        print(f"[ERROR] Reel upload failed: {ur.status_code} {ur.text}")
        return

    print(f"[REEL] Upload complete. Publishing...")

    # Step 3 — Publish the reel
    publish_payload = {
        "upload_phase":  "finish",
        "video_id":      video_id,
        "video_state":   "PUBLISHED",
        "description":   caption,
        "access_token":  FB_TOKEN,
    }
    pr = requests.post(init_url, data=publish_payload, timeout=30)
    if pr.status_code == 200:
        print(f"[REEL] Published successfully!")
    else:
        print(f"[ERROR] Reel publish failed: {pr.status_code} {pr.text}")

    # Clean up local video file
    try:
        os.remove(video_path)
    except Exception:
        pass


def create_and_post_reel(match, league_name):
    """Full pipeline — generate reel and post to Facebook."""
    home   = match["homeTeam"]["shortName"]
    away   = match["awayTeam"]["shortName"]
    goals  = match.get("goals", [])
    hs     = match["score"]["fullTime"]["home"] or 0
    as_    = match["score"]["fullTime"]["away"] or 0

    output_path = f"reel_{match['id']}.mp4"

    print(f"[REEL] Generating reel for {home} {hs}-{as_} {away}...")

    try:
        generate_reel(home, away, hs, as_, goals, league_name, output_path)

        if hs > as_:
            result = f"{home} win!"
        elif as_ > hs:
            result = f"{away} win!"
        else:
            result = "What a draw!"

        caption = (
            f"🏁 {home} {hs}-{as_} {away}\n\n"
            f"{result}\n\n"
            f"🏆 {league_name}\n\n"
            f"Follow Goal Score ZFR for live updates"
        )

        post_reel_to_facebook(output_path, caption)

    except Exception as e:
        print(f"[ERROR] Reel generation failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
