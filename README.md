# Troy Zafar Football Bot

Auto-posts goals, red cards, lineups and full time results to your Facebook page.

## Leagues Covered
- Premier League
- La Liga
- Serie A
- Champions League
- Bundesliga

## Setup Instructions

### Step 1 — Install Python
Download and install Python 3 from https://python.org

### Step 2 — Install dependencies
Open a terminal in this folder and run:
```
pip install -r requirements.txt
```

### Step 3 — Add your credentials
Open the `.env` file and fill in your 3 values:
```
FB_TOKEN=your_facebook_page_access_token_here
FB_PAGE_ID=your_facebook_page_id_here
FOOTBALL_KEY=your_football_data_api_key_here
```

### Step 4 — Run the bot
```
python run.py
```

The bot will check for match events every 60 seconds and post automatically.

## Post Format Examples

**Goal:**
```
🚩 Live: Arsenal 2-1 Chelsea

⚽ Goal: Saka (67')

📺 Premier League | Troy Zafar Football
```

**Red Card:**
```
🚩 Live: Arsenal 2-1 Chelsea

🟥 Red Card: Gallagher (71') — Chelsea

📺 Premier League | Troy Zafar Football
```

**Lineups (1 hour before kickoff):**
```
📋 Lineups: Arsenal vs Chelsea

🔵 Arsenal:
  1. Raya
  2. White
  ...

🔴 Chelsea:
  1. Sanchez
  ...

📺 Premier League | Troy Zafar Football
```

**Full Time:**
```
🏁 Full Time: Arsenal 2-1 Chelsea

Arsenal win!

📺 Premier League | Troy Zafar Football
```

## Deploying to Railway (24/7)
1. Push this folder to a GitHub repository
2. Go to railway.app and sign up
3. Click "New Project" → "Deploy from GitHub"
4. Select your repo
5. Go to Variables and add your 3 credentials there
6. Railway runs the bot 24/7 automatically
