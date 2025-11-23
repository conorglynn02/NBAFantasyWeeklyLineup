import requests
import dateutil.parser
# from dateutil.tz import gettz
import json
from datetime import date, datetime, timedelta
from itertools import combinations
from collections import defaultdict

ESPN_TO_NBA = {
    "ATL": "ATL",
    "BOS": "BOS",
    "BKN": "BKN",
    "CHA": "CHA",
    "CHI": "CHI",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GS": "GSW",
    "HOU": "HOU",
    "IND": "IND",
    "LAC": "LAC",
    "LAL": "LAL",
    "MEM": "MEM",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NO": "NOP",
    "NY": "NYK",
    "OKC": "OKC",
    "ORL": "ORL",
    "PHI": "PHI",
    "PHX": "PHX",
    "POR": "POR",
    "SAC": "SAC",
    "SA": "SAS",
    "TOR": "TOR",
    "UTAH": "UTA",
    "WSH": "WAS"
}

errors_parsing = 0

# ESPN API Weekly Fetch

def get_week_schedule(start_date, end_date):
    """Fetch all NBA games between start_date and end_date (inclusive)"""
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={start}-{end}"

    r = requests.get(url)
    r.raise_for_status()

    data = r.json()
    # with open("nba_results.json", "r") as f:
    #     data = json.load(f)
    events = data.get("events", [])
    games = []

    for event in events:
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])

        home, away = None, None
        for team in competitors:
            espn_abbr = team["team"]["abbreviation"]
            abbr = ESPN_TO_NBA.get(espn_abbr, espn_abbr)
            if team["homeAway"] == "home":
                home = abbr
            else:
                away = abbr


        event_date = extract_local_date(event)

        if home and away:
            games.append({
                "date": event_date,
                "home": home,
                "away": away
            })

    return games

def extract_local_date(event):
    """
    Parse ESPN's 'shortDetail' string, e.g.:
    '11/23 - 8:00 PM EST'
    Return a proper date object with the local game date.
    """
    short = (
        event.get("status", {})
             .get("type", {})
             .get("shortDetail", "")
    )

    # example: "11/23 - 8:00 PM EST"
    # split: ["11/23", "8:00 PM EST"]
    try:
        date_part, time_tz = short.split(" - ")
    except ValueError:
        # fallback to ESPN UTC date
        errors_parsing += 1
        return date.fromisoformat(event["date"][:10])

    # build a datetime string: "11/23 8:00 PM EST 2025"
    year = event["date"][:4]
    dt_str = f"{date_part} {time_tz} {year}"

    # use dateutil to parse including timezone abbreviations
    try:
        dt = dateutil.parser.parse(dt_str)
        return dt.date()
    except:
        errors_parsing += 1
        return date.fromisoformat(event["date"][:10])

# player availability
def teams_playing_that_day(date_games, fc_teams, bc_teams):
    """Returns the user's teams that play on that day."""
    fc_play = []
    bc_play = []

    for game in date_games:
        teams_in_game = {game["home"], game["away"]}

        for t in fc_teams:
            if t in teams_in_game:
                fc_play.append(t)

        for t in bc_teams:
            if t in teams_in_game:
                bc_play.append(t)

    return fc_play, bc_play


# lineup generation
def generate_lineups(fc_play, bc_play):
    """
    Generates all complete 5-player lineups:
    - 3 frontcourt + 2 backcourt
    - 2 frontcourt + 3 backcourt
    """
    lineups = []

    # 3F + 2B
    if len(fc_play) >= 3 and len(bc_play) >= 2:
        for fc_combo in combinations(fc_play, 3):
            for bc_combo in combinations(bc_play, 2):
                lineups.append(list(fc_combo + bc_combo))

    # 2F + 3B
    if len(fc_play) >= 2 and len(bc_play) >= 3:
        for fc_combo in combinations(fc_play, 2):
            for bc_combo in combinations(bc_play, 3):
                lineups.append(list(fc_combo + bc_combo))

    return lineups


def compute_days_playable(fc_play: list, bc_play: list) -> int:
    """
    This computes the maximum number of players that can be fielded (capped at 5).
    Returns the number of playable players for each day with the given rules:
    - Max of 3 players from either frontcourt or backcourt can play initially.
    - If the other position has at least 2 players available, the total can reach 5.
    """
    f = len(fc_play)
    b = len(bc_play)

    # each side contributes at most 3
    max_from_each = min(f, 3) + min(b, 3)

    # cap at 5 and also cannot exceed total available players
    return min(5, max_from_each, f + b)


def print_day_summary(day, fc_play, bc_play, lineups, num_games, gameday_number, teams_playing: set):
    total_players = len(fc_play) + len(bc_play)

    print(f"\n=== Gameday {gameday_number} - {day} ===")
    print(f"Number of games: {num_games}")
    print(f"Frontcourt playing ({len(fc_play)}): {', '.join(fc_play) or 'None'}")
    print(f"Backcourt playing ({len(bc_play)}): {', '.join(bc_play) or 'None'}")
    print(f"Total players available: {total_players}")
    print(f"Maximum playable players: {compute_days_playable(fc_play, bc_play)}")

    # flags
    if total_players < 5:
        print("!!  Not enough players to form a lineup!")
    elif total_players > 5 and len(lineups) == 0:
        print("!!  *Crunch day*: More than 5 players play but no legal FC/BC combinations fit 5.")
    elif total_players > 5:
        print("!!  Crunch day (you have more than 5 possible players).")

    print(f"Complete lineup combinations: {len(lineups)}")
    for i, lineup in enumerate(lineups[:10], 1):  # avoid flooding terminal
        print(f"  {i}. {lineup}")

    if len(lineups) > 10:
        print(f"  ... ({len(lineups)-10} more)")

    if total_players < 4:
        missing_teams = teams_playing - set(fc_play) - set(bc_play)
        if missing_teams:
            print(f"Teams playing that are NOT in your roster: {', '.join(sorted(missing_teams))}")

def save_run(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nSaved to {filename}")

def main():
    print("=== NBA Fantasy Weekly Lineup ===\n")

    # 1. select Monday
    monday_input = input(
        "Enter a Monday's date for a week START date (YYYY-MM-DD). Leave blank for nearest Monday in the future: "
    ).strip()

    if not monday_input:
        today = datetime.now().date()
        monday = today + timedelta(days=(7 - today.weekday()) % 7)
    else:
        monday = datetime.strptime(monday_input, "%Y-%m-%d").date()
        if monday.weekday() != 0:
            print("Warning: Provided date not Monday, adjusting to previous Monday.")
            monday = monday - timedelta(days=monday.weekday())


    sunday = monday + timedelta(days=6)
    print(f"Week selected: {monday} -> {sunday}")

    # # 2. input teams
    # print("\nEnter your 5 FRONTCOURT team abbreviations (e.g., LAL, BOS, DEN)")
    # fc_teams = input("FC teams (comma separated): ").upper().split(",")
    # fc_teams = [t.strip() for t in fc_teams if t.strip()]

    # print("\nEnter your 5 BACKCOURT team abbreviations")
    # bc_teams = input("BC teams (comma separated): ").upper().split(",")
    # bc_teams = [t.strip() for t in bc_teams if t.strip()]

    # if len(fc_teams) != 5 or len(bc_teams) != 5:
    #     print("\nERROR: You must specify exactly 5 FC teams and 5 BC teams.")
    #     return

    # hardcoding for now
    fc_teams = ["BOS", "CHA", "DEN", "WAS", "POR"]
    bc_teams = ["OKC", "PHI", "PHI", "UTA", "MIL"]

    # 3. fetch games
    print("\nFetching weekly schedule from ESPN...")
    all_games = get_week_schedule(monday, sunday)

    # organise by day
    games_by_day = defaultdict(list)
    teams_playing_each_day = defaultdict(set)
    for g in all_games:
        teams_playing_each_day[g["date"]].add(g["home"])
        teams_playing_each_day[g["date"]].add(g["away"])
        # appends the game 'g' to the list of games for the date 'g["date"]' in the 'games_by_day' dictionary.
        games_by_day[g["date"]].append(g)

    # group teams by number of games this week
    team_counts = defaultdict(int)
    for g in all_games:
        # count both home and away as a game for that team
        team_counts[g["home"]] += 1
        team_counts[g["away"]] += 1

    # invert into groups: count -> [teams]
    groups = defaultdict(list)
    for team, cnt in team_counts.items():
        groups[cnt].append(team)

    print("\nTeams grouped by number of games this week:")
    if not groups:
        print("No games found this week")
    else:
        for cnt in sorted(groups.keys(), reverse=True):
            teams = ", ".join(sorted(groups[cnt]))
            print(f"  {cnt} game{'s' if cnt != 1 else ''}: {teams}")

    # 4. analyse each day
    results = {}
    gameday_counter = 0
    weeks_playable_players = 0
    num_weekly_games_for_squad = {t: 0 for t in fc_teams + bc_teams}
    print("\n=== WEEK SUMMARY ===")
    for i in range(7):
        day = monday + timedelta(days=i)
        day_games = games_by_day[day]

        # which teams play
        fc_play, bc_play = teams_playing_that_day(day_games, fc_teams, bc_teams)
        teams_playing_today = set()
        for t in fc_play + bc_play:
            if t not in teams_playing_today:
                teams_playing_today.add(t)
                num_weekly_games_for_squad[t] += 1
        this_days_playable_players = compute_days_playable(fc_play, bc_play)
        weeks_playable_players += this_days_playable_players
        num_games = len(day_games)

        # lineups
        lineups = generate_lineups(fc_play, bc_play)

        # print summary
        if num_games != 0:
            gameday_counter += 1
            print_day_summary(day, fc_play, bc_play, lineups, num_games, gameday_counter, teams_playing_each_day[day])
        else:
            print(f"\n=== Not a Gameday - {day} ===")
            print("No games scheduled.")

        # save structured result
        results[str(day)] = {
            "fc_play": fc_play,
            "bc_play": bc_play,
            "lineups": lineups,
            "playable_players": this_days_playable_players
        }

    print(f"\nTotal playable players for the week (capped at 5 per day): {weeks_playable_players}")
    print(f"Total possible players for the week: {5 * gameday_counter}")
    print(f"Number of days with 0 playable players: {sum(1 for d in results.values() if d['playable_players'] == 0)}")
    print(f"Number of days with 1 playable players: {sum(1 for d in results.values() if d['playable_players'] == 1)}")
    print(f"Number of days with 2 playable players: {sum(1 for d in results.values() if d['playable_players'] == 2)}")
    print(f"Number of days with 3 playable players: {sum(1 for d in results.values() if d['playable_players'] == 3)}")
    print(f"Number of days with 4 playable players: {sum(1 for d in results.values() if d['playable_players'] == 4)}")
    print(f"Number of days with 5 playable players: {sum(1 for d in results.values() if d['playable_players'] == 5)}")
    print(f"Average playable players per day: {weeks_playable_players / gameday_counter:.2f}")

    print("\nSquad grouped by number of games this week:")
    if not num_weekly_games_for_squad:
        print("No games found this week")
    else:
        groups = defaultdict(list)
        for team, cnt in num_weekly_games_for_squad.items():
            groups[cnt].append(team)
        for cnt in sorted(groups.keys(), reverse=True):
            teams = ", ".join(sorted(groups[cnt]))
            print(f"  {cnt} game{'s' if cnt != 1 else ''}: {teams}")

    if errors_parsing > 0:
        print(f"\nNote: There were {errors_parsing} errors parsing game data.")

    # 5. save?
    # save_ans = input("\nSave results to last_run.json? (y/n): ").strip().lower()
    # if save_ans == "y":
    #     save_run("last_run.json", {
    #         "week_start": monday,
    #         "week_end": sunday,
    #         "fc_teams": fc_teams,
    #         "bc_teams": bc_teams,
    #         "results": results,
    #         "weeks_playable_players": weeks_playable_players
    #     })

    print("\nDone.")


if __name__ == "__main__":
    main()
