"""
fetch_stats.py
---------------
Adds match "insights" for markets most odds APIs don't cover well -
corners and cards - using API-Football's free tier (https://api-sports.io).

IMPORTANT DIFFERENCE from fetch_data.py: these numbers are NOT compared
against bookmaker odds. They're simply recent match averages - useful
as your own judgement for building bets on corners/cards markets, but
they are statistical estimates, not verified "value" like the rest of
the site. The website labels them clearly as such.

Because the free API-Football tier only allows 100 requests/day, this
script deliberately:
  - covers ONE league to start (Premier League) - add more via LEAGUES
  - only looks at a handful of upcoming fixtures
  - is meant to run once a day (see update-stats.yml), not every 3 hours

Read the comments below to see how to safely extend the numbers.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone

API_KEY = os.environ.get("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# League IDs from API-Football. Add more here once you're comfortable -
# full list: https://www.api-football.com/documentation-v3#tag/Leagues
LEAGUES = {
    39: "Premier League",
}

SEASON = 2025                        # update this each new football season
UPCOMING_FIXTURES_PER_LEAGUE = 5     # keep low - each fixture costs ~8 requests
RECENT_MATCHES_TO_AVERAGE = 3        # how many past matches to average over


# ---------------------------------------------------------------------
# Small helper for calling the API-Football REST endpoints
# ---------------------------------------------------------------------

def get(endpoint, params):
    response = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("response", [])


def normalise(name):
    """Used to help match team names against the odds site's data later."""
    return (
        name.lower()
        .replace("fc", "")
        .replace("afc", "")
        .replace(".", "")
        .strip()
    )


# ---------------------------------------------------------------------
# Work out a team's recent average corners / yellow cards
# ---------------------------------------------------------------------

# Cache so we don't re-fetch the same team twice in one run (saves quota
# when a team appears in more than one upcoming fixture).
_team_stats_cache = {}

def average_team_stats(team_id):
    if team_id in _team_stats_cache:
        return _team_stats_cache[team_id]

    recent = get("fixtures", {
        "team": team_id,
        "last": RECENT_MATCHES_TO_AVERAGE,
        "status": "FT",
    })

    corners, cards = [], []
    for fixture in recent:
        fixture_id = fixture["fixture"]["id"]
        stats = get("fixtures/statistics", {"fixture": fixture_id, "team": team_id})
        for block in stats:
            for item in block.get("statistics", []):
                if item["type"] == "Corner Kicks" and item["value"] is not None:
                    corners.append(item["value"])
                if item["type"] == "Yellow Cards" and item["value"] is not None:
                    cards.append(item["value"])
        time.sleep(0.3)  # be polite to the free tier rate limit

    result = {
        "matches_used": len(recent),
        "avg_corners": round(sum(corners) / len(corners), 1) if corners else None,
        "avg_yellow_cards": round(sum(cards) / len(cards), 1) if cards else None,
    }
    _team_stats_cache[team_id] = result
    return result


# ---------------------------------------------------------------------
# Run everything and save the result
# ---------------------------------------------------------------------

def main():
    if not API_KEY:
        print("ERROR: API_FOOTBALL_KEY environment variable is not set.")
        print("Locally: export API_FOOTBALL_KEY=your_key_here")
        print("On GitHub: add it as a repository secret (see README.md)")
        return

    insights = []

    for league_id, league_name in LEAGUES.items():
        print(f"Fetching upcoming {league_name} fixtures...")
        fixtures = get("fixtures", {
            "league": league_id,
            "season": SEASON,
            "next": UPCOMING_FIXTURES_PER_LEAGUE,
        })

        for fixture in fixtures:
            home = fixture["teams"]["home"]
            away = fixture["teams"]["away"]
            print(f"  Averaging stats for {home['name']} vs {away['name']}...")

            home_stats = average_team_stats(home["id"])
            away_stats = average_team_stats(away["id"])

            combined_corners = None
            if home_stats["avg_corners"] is not None and away_stats["avg_corners"] is not None:
                combined_corners = round(home_stats["avg_corners"] + away_stats["avg_corners"], 1)

            combined_cards = None
            if home_stats["avg_yellow_cards"] is not None and away_stats["avg_yellow_cards"] is not None:
                combined_cards = round(home_stats["avg_yellow_cards"] + away_stats["avg_yellow_cards"], 1)

            insights.append({
                "league": league_name,
                "match": f"{home['name']} vs {away['name']}",
                "home_team": home["name"],
                "away_team": away["name"],
                "match_key": f"{normalise(home['name'])}_vs_{normalise(away['name'])}",
                "commence_time": fixture["fixture"]["date"],
                "home_team_avg_corners": home_stats["avg_corners"],
                "away_team_avg_corners": away_stats["avg_corners"],
                "estimated_total_corners": combined_corners,
                "home_team_avg_yellow_cards": home_stats["avg_yellow_cards"],
                "away_team_avg_yellow_cards": away_stats["avg_yellow_cards"],
                "estimated_total_yellow_cards": combined_cards,
                "based_on_last_n_matches": RECENT_MATCHES_TO_AVERAGE,
            })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insight_count": len(insights),
        "insights": insights,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/stats.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(insights)} match insights to data/stats.json")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------
# HOW TO EXTEND THIS:
#
# 1. More leagues: add entries to LEAGUES, e.g. 140 for La Liga,
#    135 for Serie A. Watch your daily request quota as you add more -
#    each fixture costs roughly 2 (last-5 lookup) + up to 6 (stats
#    calls) = 8 requests per fixture, times 2 teams... it adds up fast.
#
# 2. Other stats: the "statistics" array from /fixtures/statistics
#    also includes shots on goal, possession, fouls, offsides, and
#    more. Add another `if item["type"] == "..."` block above to
#    track any of them the same way corners/cards are tracked.
#
# 3. Basketball fouls: API-Basketball (same account, different base
#    URL: https://v1.basketball.api-sports.io) has an equivalent
#    fixtures/statistics endpoint if you want to add a fouls-based
#    insight for NBA games later.
# ---------------------------------------------------------------------
