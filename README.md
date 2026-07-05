# Line Watch — Live Sports Betting Tips Site

A self-updating website that pulls real bookmaker odds for football,
basketball, and tennis, and highlights potential value bets. It runs
entirely on free GitHub tools: **GitHub Actions** refreshes the data on
a schedule, and **GitHub Pages** hosts the site itself.

## How it works

```
GitHub Actions (runs every 3 hours)
        │
        ▼
 fetch_data.py  ──►  data/tips.json  ──►  index.html (what visitors see)
```

## Setup — step by step

### 1. Get a free API key
1. Go to https://the-odds-api.com and sign up for the free tier.
2. Copy your API key from your account dashboard.

### 2. Create your GitHub repository
1. On GitHub, click **New repository**. Name it anything, e.g. `line-watch`.
   Make it **Public** (required for free GitHub Pages + Actions on the free plan).
2. Upload all the files in this folder to that repository — either by
   dragging them into the GitHub web UI, or with git:
   ```bash
   git init
   git add .
   git commit -m "Initial site"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/line-watch.git
   git push -u origin main
   ```

### 3. Add your API key as a secret (keep it private!)
1. In your repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `ODDS_API_KEY`   Value: (paste your key from step 1)
4. Save.

This means your key is never visible in your code or to site visitors —
only the Action running in the background can use it.

### 4. Turn on GitHub Pages
1. Go to **Settings → Pages**.
2. Under "Build and deployment", set **Source** to `Deploy from a branch`.
3. Branch: `main`, folder: `/ (root)`. Save.
4. Your site will appear at `https://YOUR_USERNAME.github.io/line-watch/`
   within a minute or two.

### 5. Run the data fetch for the first time
1. Go to the **Actions** tab in your repo.
2. Click on the **Update betting tips** workflow.
3. Click **Run workflow** (this triggers it manually instead of waiting
   for the schedule).
4. After it finishes (~30 seconds), refresh your website — you should
   see real tips appear.

From now on, it runs automatically every 3 hours, all by itself.

## Running it on your own computer (optional, for testing)

```bash
pip install -r requirements.txt
export ODDS_API_KEY=your_key_here      # on Windows: set ODDS_API_KEY=your_key_here
python fetch_data.py
```

Then open `index.html` in your browser (or better, run a local server:
`python -m http.server` and visit `http://localhost:8000`).

## Changing how often it updates

Edit `.github/workflows/update.yml` and change this line:
```yaml
- cron: "0 */3 * * *"   # every 3 hours
```
Cron format is `minute hour day month weekday`. For example, `0 */1 * * *`
runs every hour. Don't go too frequent — the free API tier has a monthly
request cap.

## Adding more sports or leagues

Open `fetch_data.py` and add entries to the `SPORTS` dictionary near the
top. Full list of available sport keys:
https://the-odds-api.com/sports-odds-data/sports-apis.html

## Making the tips smarter

Right now, `fetch_data.py` only compares bookmakers against each other.
The natural next step is to pull in real team/player stats (recent form,
head-to-head record, injuries) from a stats API like API-Football,
API-Basketball, or API-Tennis (all under https://api-sports.io), and
calculate your own win-probability estimate. Compare that number to the
bookmaker's implied probability — when yours is meaningfully higher,
that's a genuine statistically-driven tip rather than just a
bookmaker-disagreement signal. There's a longer comment block at the
bottom of `fetch_data.py` with pointers on where to start.

## Legal & responsible gambling note

Betting-tips content is legal to publish, but if you ever add
affiliate links or ads, check the advertising standards for gambling
content in your jurisdiction (in the UK: ASA / Gambling Commission
guidance) — you'll typically need clear 18+ and "gamble responsibly"
messaging, which is already included on the site.
