"""
fetch_data.py
--------------
This script is the "brain" of the site. Every time it runs, it:

1. Calls The Odds API to get upcoming fixtures + bookmaker odds for
   football (soccer), basketball, and tennis - across THREE markets:
     - h2h     (match winner / moneyline)
     - totals  (over/under goals, points, or games)
     - spreads (handicap)
2. Works out the "implied probability" each bookmaker's odds represent.
3. Compares bookmakers against each other to find the best available
   price for each outcome (a simple, honest starting model).
4. Saves everything into data/tips.json, which the website reads.

Note: corners, cards, and player props aren't covered here - free odds
APIs generally don't carry those markets. See fetch_stats.py for a
separate, stats-based (not bookmaker-odds-based) way to estimate those.

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

# Which markets to pull. Each additional market costs more of your
# monthly request quota, so keep an eye on usage if you add more sports.
# h2h = match winner, totals = over/under, spreads = handicap
MARKETS = "h2h,totals,spreads"

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
        "markets": MARKETS,
        "oddsFormat": "decimal",
    }
    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        print(f"  ! Could not fetch {sport_key}: {response.status_code} {response.text[:200]}")
        return []

    return response.json()


# ---------------------------------------------------------------------
# STEP 2: Turn raw odds into tips, organised by market
# ---------------------------------------------------------------------

def implied_probability(decimal_odds):
    """Decimal odds of 2.00 means a 50% implied chance of winning."""
    return 1 / decimal_odds


def analyse_market(bookmakers, market_key):
    """
    Looks across every bookmaker offering this market on this game and:
      - finds the best (highest) price for each outcome
      - flags the outcome where bookmakers most disagree with each
        other as the closest thing we have right now to a "value" tip

    For totals/spreads, outcomes with different lines (e.g. Over 2.5 vs
    Over 3.5) are kept separate, since they're not really the same bet.
    """
    # outcome_prices key = (selection name, line/point if any)
    outcome_prices = {}

    for bookmaker in bookmakers:
        for market in bookmaker.get("markets", []):
            if market["key"] != market_key:
                continue
            for outcome in market["outcomes"]:
                name = outcome["name"]
                point = outcome.get("point")  # e.g. 2.5 for "Over 2.5"
                price = outcome["price"]
                key = (name, point)
                outcome_prices.setdefault(key, []).append(price)

    if not outcome_prices:
        return []

    analysis = []
    for (name, point), prices in outcome_prices.items():
        best = max(prices)
        avg = sum(prices) / len(prices)
        label = f"{name} {point}" if point is not None else name
        analysis.append({
            "selection": label,
            "point": point,
            "best_odds": round(best, 2),
            "average_odds": round(avg, 2),
            "implied_probability_pct": round(implied_probability(avg) * 100, 1),
            "num_bookmakers": len(prices),
        })

    # Sort so the outcome with the biggest best-vs-average gap comes first
    analysis.sort(key=lambda a: a["best_odds"] - a["average_odds"], reverse=True)
    return analysis


def build_tip(game, sport_label):
    """Builds the full multi-market tip object for a single fixture."""
    bookmakers = game.get("bookmakers", [])
    if not bookmakers:
        return None

    markets = {}
    for market_key in MARKETS.split(","):
        selections = analyse_market(bookmakers, market_key)
        if selections:
            markets[market_key] = selections

    if not markets:
        return None

    # Keep a single "top_tip" for the scrolling ticker - prefer h2h,
    # otherwise fall back to whatever market we do have.
    top_tip = None
    if "h2h" in markets:
        top_tip = markets["h2h"][0]
    else:
        top_tip = next(iter(markets.values()))[0]

    return {
        "sport": sport_label,
        "match": f"{game.get('home_team')} vs {game.get('away_team')}",
        "commence_time": game.get("commence_time"),
        "top_tip": top_tip,
        "markets": markets,
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
#    against each other, pull team/player stats and calculate YOUR OWN
#    estimated probability. Compare that to the bookmaker's implied
#    probability - if yours is higher, that's a genuine "value bet"
#    signal, not just a bookmaker disagreement.
#
# 2. Corners, cards, player props: see fetch_stats.py, which builds
#    these from raw match statistics rather than bookmaker odds (most
#    free odds APIs don't carry these markets).
#
# 3. More leagues: add more sport_key entries to SPORTS. Full list at
#    https://the-odds-api.com/sports-odds-data/sports-apis.html
# ---------------------------------------------------------------------
