"""
fetch_data.py
--------------
This script is the "brain" of the site. Every time it runs, it:

1. Calls The Odds API to get upcoming fixtures + bookmaker odds for
   football (soccer), basketball, and tennis.
2. Works out the "implied probability" each bookmaker's odds represent.
3. Compares bookmakers against each other to find the best available
   price for each outcome (a simple, honest starting model).
4. Saves everything into data/tips.json, which the website reads.

You don't need to understand every line to use this. Read the comments
(the lines starting with #) to see what each part does, and the
"HOW TO EXTEND THIS" section at the bottom for where to add your own
smarter prediction logic later.
"""

import os
import json
import requests
from datetime import datetime, timezone

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

# Your API key is read from an environment variable, NOT written here.
# This keeps it secret and out of your public GitHub repo.
API_KEY = os.environ.get("ODDS_API_KEY")

# The Odds API "sport keys" for the sports we care about.
# Full list: https://the-odds-api.com/sports-odds-data/sports-apis.html
SPORTS = {
    "soccer_epl": "Football (Premier League)",
    "basketball_nba": "Basketball (NBA)",
    "tennis_atp_wimbledon": "Tennis (ATP Wimbledon)",
}

BASE_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

# ---------------------------------------------------------------------
# STEP 1: Fetch odds for one sport from The Odds API
# ---------------------------------------------------------------------

def fetch_odds(sport_key):
    """Ask The Odds API for upcoming games + odds for a single sport."""
    url = BASE_URL.format(sport=sport_key)
    params = {
        "apiKey": API_KEY,
        "regions": "uk",       # bookmakers to use: uk, us, eu, au
        "markets": "h2h",      # h2h = head-to-head / moneyline (simplest market)
        "oddsFormat": "decimal",
    }
    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        print(f"  ! Could not fetch {sport_key}: {response.status_code} {response.text[:200]}")
        return []

    return response.json()


# ---------------------------------------------------------------------
# STEP 2: Turn raw odds into a simple "tip"
# ---------------------------------------------------------------------

def implied_probability(decimal_odds):
    """Decimal odds of 2.00 means a 50% implied chance of winning."""
    return 1 / decimal_odds


def build_tip(game, sport_label):
    """
    Looks across every bookmaker offering odds on this game and:
      - finds the best (highest) price for each team/outcome
      - flags the outcome where bookmakers most disagree with each
        other as the closest thing we have right now to a "value" tip

    This is intentionally simple to start with. See "HOW TO EXTEND
    THIS" below for how to fold in real player/team form data.
    """
    bookmakers = game.get("bookmakers", [])
    if not bookmakers:
        return None

    # Collect all prices quoted for each outcome (e.g. each team name)
    outcome_prices = {}
    for bookmaker in bookmakers:
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market["outcomes"]:
                name = outcome["name"]
                price = outcome["price"]
                outcome_prices.setdefault(name, []).append(price)

    if not outcome_prices:
        return None

    # For each outcome, work out the best odds and the average odds.
    # A big gap between "best" and "average" can indicate value.
    analysis = []
    for name, prices in outcome_prices.items():
        best = max(prices)
        avg = sum(prices) / len(prices)
        analysis.append({
            "selection": name,
            "best_odds": round(best, 2),
            "average_odds": round(avg, 2),
            "implied_probability_pct": round(implied_probability(avg) * 100, 1),
            "num_bookmakers": len(prices),
        })

    # Sort so the outcome with the biggest best-vs-average gap comes first
    analysis.sort(key=lambda a: a["best_odds"] - a["average_odds"], reverse=True)

    return {
        "sport": sport_label,
        "match": f"{game.get('home_team')} vs {game.get('away_team')}",
        "commence_time": game.get("commence_time"),
        "top_tip": analysis[0],
        "all_selections": analysis,
    }


# ---------------------------------------------------------------------
# STEP 3: Run everything and save the result
# ---------------------------------------------------------------------

def main():
    if not API_KEY:
        print("ERROR: ODDS_API_KEY environment variable is not set.")
        print("Locally: export ODDS_API_KEY=your_key_here")
        print("On GitHub: add it as a repository secret (see README.md)")
        return

    all_tips = []

    for sport_key, sport_label in SPORTS.items():
        print(f"Fetching {sport_label}...")
        games = fetch_odds(sport_key)
        for game in games:
            tip = build_tip(game, sport_label)
            if tip:
                all_tips.append(tip)

    # Sort tips by kickoff time, soonest first
    all_tips.sort(key=lambda t: t["commence_time"])

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tip_count": len(all_tips),
        "tips": all_tips,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tips.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(all_tips)} tips to data/tips.json")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------
# HOW TO EXTEND THIS (once you're comfortable with the basics):
#
# 1. Real predictive modelling: instead of only comparing bookmakers
#    against each other, pull team/player stats from API-Football /
#    API-Basketball / API-Tennis (recent form, head-to-head history,
#    injuries) and calculate YOUR OWN estimated probability. Compare
#    that to the bookmaker's implied probability - if yours is higher,
#    that's a genuine "value bet" signal, not just a bookmaker
#    disagreement.
#
# 2. More markets: add "spreads" (handicap) and "totals" (over/under)
#    to the `markets` parameter above, e.g. "h2h,spreads,totals".
#
# 3. More leagues: add more sport_key entries to SPORTS. Full list at
#    https://the-odds-api.com/sports-odds-data/sports-apis.html
# ---------------------------------------------------------------------
