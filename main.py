import requests
import sqlite3
import time
import sys
from bs4 import BeautifulSoup
from dataclasses import dataclass

# Constants
RL_DB_NAME = "rate_limiter.db"
STATS_DB_NAME = "nba_stats.db"
SEASON_STATS_DB_NAME = "nba_season_totals.db"
SCHEDULE_DB_NAME = "nba_schedules.db"

TEAM_TO_CODE = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BRK",
    "Charlotte Hornets": "CHO",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

MAX_CALLS = 19
WINDOW_SIZE = 60


# Data structures used throughout the program.  Many of the original notes
# described output as dataclasses; the implementation now reflects that by
# returning typed objects instead of raw dictionaries.
@dataclass
class Game:
    """Represents a single game for a team schedule.

    Attributes:
        game_id: key string like '20240216LALGSW'
        team_code: three-letter team code (e.g. 'LAL').
        date: string representation of the game date.
        opponent: opponent team name as shown on schedule page.
    """

    game_id: str
    team_code: str
    date: str
    opponent: str


@dataclass
class PlayerGamePerformance:
    """Box‑score stats for a single player in one game.

    The fields mirror the columns stored in :file:`nba_stats.db`.
    """

    game_id: str
    team: str
    player_name: str
    mp: str
    fg: int
    fga: int
    fg_pct: float
    fg3: int
    fg3a: int
    fg3_pct: float
    ft: int
    fta: int
    ft_pct: float
    orb: int
    drb: int
    trb: int
    ast: int
    stl: int
    blk: int
    tov: int
    pf: int
    pts: int
    plus_minus: str


@dataclass
class SeasonPlayerStats:
    """Per‑game season averages for a player on a team.

    Corresponds to rows stored in :file:`nba_season_totals.db`.
    """

    year: int
    team: str
    player_name: str
    mp: float
    fg: float
    fga: float
    fg_pct: float
    fg3: float
    fg3a: float
    fg3_pct: float
    ft: float
    fta: float
    ft_pct: float
    orb: float
    drb: float
    trb: float
    ast: float
    stl: float
    blk: float
    tov: float
    pf: float
    pts: float


@dataclass
class StatOutlier:
    """Represents how a single game stat compares to the season average."""

    name: str
    stat: str
    val: float
    avg: float
    pct: float


# Database Initialization

# ---------------------------------------------------------------------------
# Database clearing utilities
# ---------------------------------------------------------------------------


def clear_rl_db():
    """Remove all stored timestamps from the rate limiter database."""
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("DELETE FROM api_calls")


def clear_stats_db():
    """Delete every row from the player performance database."""
    with sqlite3.connect(STATS_DB_NAME) as conn:
        conn.execute("DELETE FROM player_performances")


def clear_season_db():
    """Purge all season-average records."""
    with sqlite3.connect(SEASON_STATS_DB_NAME) as conn:
        conn.execute("DELETE FROM season_performances")


def clear_schedule_db():
    """Remove all saved schedule entries."""
    with sqlite3.connect(SCHEDULE_DB_NAME) as conn:
        conn.execute("DELETE FROM team_schedule")


def clear_all_dbs():
    """Convenience helper to wipe every database managed by this module."""
    clear_rl_db()
    clear_stats_db()
    clear_season_db()
    clear_schedule_db()


def init_rl_db():
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS api_calls (timestamp REAL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON api_calls(timestamp)")


def init_stats_db():
    with sqlite3.connect(STATS_DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_performances (
                game_id TEXT, team TEXT, player_name TEXT, mp TEXT, 
                fg INT, fga INT, fg_pct REAL, fg3 INT, fg3a INT, fg3_pct REAL,
                ft INT, fta INT, ft_pct REAL, orb INT, drb INT, trb INT, 
                ast INT, stl INT, blk INT, tov INT, pf INT, pts INT, plus_minus TEXT,
                PRIMARY KEY (game_id, player_name)
            )
        """
        )


def init_season_db():
    with sqlite3.connect(SEASON_STATS_DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS season_performances (
                year INT, team TEXT, player_name TEXT, mp REAL, 
                fg REAL, fga REAL, fg_pct REAL, fg3 REAL, fg3a REAL, fg3_pct REAL,
                ft REAL, fta REAL, ft_pct REAL, orb REAL, drb REAL, trb REAL, 
                ast REAL, stl REAL, blk REAL, tov REAL, pf REAL, pts REAL,
                PRIMARY KEY (year, team, player_name)
            )
        """
        )


def init_schedule_db():
    with sqlite3.connect(SCHEDULE_DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_schedule (
                game_id TEXT PRIMARY KEY, team_code TEXT, date TEXT, opponent TEXT
            )
        """
        )


def init_all_dbs():
    init_rl_db()
    init_stats_db()
    init_season_db()
    init_schedule_db()


# Rate Limiter
def get_current_window_count():
    now = time.time()
    cutoff = now - WINDOW_SIZE
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("DELETE FROM api_calls WHERE timestamp < ?", (cutoff,))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM api_calls WHERE timestamp >= ?", (cutoff,)
        )
        return cursor.fetchone()[0]


def log_call():
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("INSERT INTO api_calls (timestamp) VALUES (?)", (time.time(),))


def guarded_fetch(url):
    while True:
        count = get_current_window_count()
        if count < MAX_CALLS:
            log_call()
            print(f"Requesting: {url} (Window count: {count + 1})")
            response = requests.get(url)
            if response.status_code == 429:
                print("Hit 429 (Rate Limit)")
                continue
            return response.text
        else:
            print(f"Limit reached ({count}/{MAX_CALLS}).")


# Database
def save_to_db(data_list):
    """Insert or replace a list of player-game stats into the database.

    The items may be dictionaries or :class:`PlayerGamePerformance` objects.  A
    dataclass will be converted via ``.__dict__``.

    Args:
        data_list: iterable of statistics to persist.
    """
    if not data_list:
        return
    columns = [
        "game_id",
        "team",
        "player_name",
        "mp",
        "fg",
        "fga",
        "fg_pct",
        "fg3",
        "fg3a",
        "fg3_pct",
        "ft",
        "fta",
        "ft_pct",
        "orb",
        "drb",
        "trb",
        "ast",
        "stl",
        "blk",
        "tov",
        "pf",
        "pts",
        "plus_minus",
    ]
    placeholders = ", ".join(["?" for _ in columns])
    query = f"INSERT OR REPLACE INTO player_performances ({', '.join(columns)}) VALUES ({placeholders})"
    with sqlite3.connect(STATS_DB_NAME) as conn:
        rows = []
        for item in data_list:
            if isinstance(item, PlayerGamePerformance):
                d = item.__dict__
            else:
                d = item
            rows.append(tuple(d.get(col) for col in columns))
        conn.executemany(query, rows)


def save_season_to_db(data_list):
    """Persist season averages to the season database.

    Accepts either raw dicts or :class:`SeasonPlayerStats` objects.
    """
    if not data_list:
        return
    columns = [
        "year",
        "team",
        "player_name",
        "mp",
        "fg",
        "fga",
        "fg_pct",
        "fg3",
        "fg3a",
        "fg3_pct",
        "ft",
        "fta",
        "ft_pct",
        "orb",
        "drb",
        "trb",
        "ast",
        "stl",
        "blk",
        "tov",
        "pf",
        "pts",
    ]
    placeholders = ", ".join(["?" for _ in columns])
    query = f"INSERT OR REPLACE INTO season_performances ({', '.join(columns)}) VALUES ({placeholders})"
    with sqlite3.connect(SEASON_STATS_DB_NAME) as conn:
        rows = []
        for item in data_list:
            if isinstance(item, SeasonPlayerStats):
                d = item.__dict__
            else:
                d = item
            rows.append(tuple(d.get(col) for col in columns))
        conn.executemany(query, rows)


def save_schedule_to_db(data_list):
    """Write schedule entries to the schedule database.

    ``data_list`` can contain :class:`Game` instances or raw dicts.
    """
    if not data_list:
        return
    columns = ["game_id", "team_code", "date", "opponent"]
    placeholders = ", ".join(["?" for _ in columns])
    query = f"INSERT OR REPLACE INTO team_schedule ({', '.join(columns)}) VALUES ({placeholders})"
    with sqlite3.connect(SCHEDULE_DB_NAME) as conn:
        rows = []
        for item in data_list:
            if isinstance(item, Game):
                d = item.__dict__
            else:
                d = item
            rows.append(tuple(d.get(col) for col in columns))
        conn.executemany(query, rows)


# Parsing


def extract_player_stats(row, game_id, team_code):
    """Internal helper used by :func:`parse_box_score`.

    The value returned is a **dict** mirroring the keys used by the
    :class:`PlayerGamePerformance` dataclass.  It is converted to the
    dataclass later so that callers only ever see typed objects.

    Args:
        row: soup element corresponding to a single <tr> in the box score
        game_id: string id of the game being scraped
        team_code: the three‑letter team code for the table being processed

    Returns:
        dict with raw string values or ``None`` if the row doesn't contain player
        data (header rows, etc.).
    """
    if row.get("class") and "thead" in row.get("class"):
        return None
    name_cell = row.find("th", {"data-stat": "player"})
    if not name_cell:
        return None
    p = {"game_id": game_id, "team": team_code, "player_name": name_cell.get_text()}
    for td in row.find_all("td"):
        stat_name = td.get("data-stat")
        p[stat_name] = td.get_text()
    return p


def parse_box_score(html_content, game_id):
    """Parse the HTML of a box score page and return a list of
    :class:`PlayerGamePerformance` objects.

    Args:
        html_content: raw HTML string downloaded from basketball-reference
        game_id: identifier parsed from the box score URL

    Returns:
        ``List[PlayerGamePerformance]``.  Empty list if nothing could be found
        (e.g. malformed page).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    raw_players = []
    tables = soup.find_all("table", id=lambda x: x and x.endswith("-game-basic"))
    for table in tables:
        try:
            team_code = table.get("id").split("-")[1]
            rows = table.find("tbody").find_all("tr")
            for row in rows:
                player_data = extract_player_stats(row, game_id, team_code)
                if player_data:
                    raw_players.append(player_data)
        except (IndexError, AttributeError):
            continue

    # convert raw dicts into dataclasses with correct types
    result = []
    for d in raw_players:
        try:
            perf = PlayerGamePerformance(
                game_id=d.get("game_id"),
                team=d.get("team"),
                player_name=d.get("player_name"),
                mp=d.get("mp", ""),
                fg=int(d.get("fg") or 0),
                fga=int(d.get("fga") or 0),
                fg_pct=float(d.get("fg_pct") or 0),
                fg3=int(d.get("fg3") or 0),
                fg3a=int(d.get("fg3a") or 0),
                fg3_pct=float(d.get("fg3_pct") or 0),
                ft=int(d.get("ft") or 0),
                fta=int(d.get("fta") or 0),
                ft_pct=float(d.get("ft_pct") or 0),
                orb=int(d.get("orb") or 0),
                drb=int(d.get("drb") or 0),
                trb=int(d.get("trb") or 0),
                ast=int(d.get("ast") or 0),
                stl=int(d.get("stl") or 0),
                blk=int(d.get("blk") or 0),
                tov=int(d.get("tov") or 0),
                pf=int(d.get("pf") or 0),
                pts=int(d.get("pts") or 0),
                plus_minus=d.get("plus_minus", ""),
            )
            result.append(perf)
        except Exception:
            # if for whatever reason the conversion fails just skip the row
            continue
    return result


def parse_team_season(html_content, team_code, year):
    """Parse a team page for a given year and return per‑game stats.

    Args:
        html_content: raw HTML of the team/year page
        team_code: three‑letter team code used for normalization/storage
        year: integer season year

    Returns:
        ``List[SeasonPlayerStats]``.  Empty list if the page lacks the
        per‑game table (e.g. before the team existed).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="per_game_stats")
    if not table:
        return []
    raw_players = []
    rows = table.find("tbody").find_all("tr")
    mapping = {
        "mp": "mp_per_g",
        "fg": "fg_per_g",
        "fga": "fga_per_g",
        "fg_pct": "fg_pct",
        "fg3": "fg3_per_g",
        "fg3a": "fg3a_per_g",
        "fg3_pct": "fg3_pct",
        "ft": "ft_per_g",
        "fta": "fta_per_g",
        "ft_pct": "ft_pct",
        "orb": "orb_per_g",
        "drb": "drb_per_g",
        "trb": "trb_per_g",
        "ast": "ast_per_g",
        "stl": "stl_per_g",
        "blk": "blk_per_g",
        "tov": "tov_per_g",
        "pf": "pf_per_g",
        "pts": "pts_per_g",
    }
    for row in rows:
        # ignore additional header rows that may appear inside tbody
        if row.get("class") and "thead" in row.get("class"):
            continue
        # player names can be wrapped in <th> or <td> depending on html
        # modern team pages use data-stat="name_display" while older tables
        # (and some other pages) use "player".  Accept either value.
        name_cell = row.find(
            lambda tag: tag.name in ("td", "th")
            and tag.get("data-stat") in ("player", "name_display")
        )
        if not name_cell:
            continue
        player_data = {
            "year": year,
            "team": team_code,
            "player_name": name_cell.get_text(),
        }
        for db_key, html_id in mapping.items():
            cell = row.find("td", {"data-stat": html_id})
            player_data[db_key] = cell.get_text() if cell else "0"
        raw_players.append(player_data)

    # convert to dataclasses with numeric typing
    result = []
    for d in raw_players:
        try:
            stats = SeasonPlayerStats(
                year=d.get("year"),
                team=d.get("team"),
                player_name=d.get("player_name"),
                mp=float(d.get("mp") or 0),
                fg=float(d.get("fg") or 0),
                fga=float(d.get("fga") or 0),
                fg_pct=float(d.get("fg_pct") or 0),
                fg3=float(d.get("fg3") or 0),
                fg3a=float(d.get("fg3a") or 0),
                fg3_pct=float(d.get("fg3_pct") or 0),
                ft=float(d.get("ft") or 0),
                fta=float(d.get("fta") or 0),
                ft_pct=float(d.get("ft_pct") or 0),
                orb=float(d.get("orb") or 0),
                drb=float(d.get("drb") or 0),
                trb=float(d.get("trb") or 0),
                ast=float(d.get("ast") or 0),
                stl=float(d.get("stl") or 0),
                blk=float(d.get("blk") or 0),
                tov=float(d.get("tov") or 0),
                pf=float(d.get("pf") or 0),
                pts=float(d.get("pts") or 0),
            )
            result.append(stats)
        except Exception:
            continue
    return result


def parse_team_schedule(html_content, team_code):
    """Scrape the schedule table for a team/year and return
    ``List[Game]``.

    Args:
        html_content: the raw html from a /teams/XYZ/YYYY_games.html page
        team_code: three-letter code used on the page (e.g. "LAL").

    Returns:
        list of :class:`Game` objects.  An empty list indicates the schedule
        table couldn't be found (novice seasons, etc.).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="games")
    if not table:
        return []
    games = []
    rows = table.find("tbody").find_all("tr")
    for row in rows:
        if row.get("class") and "thead" in row.get("class"):
            continue
        box_score_cell = row.find("td", {"data-stat": "box_score_text"})
        if not box_score_cell or not box_score_cell.find("a"):
            continue
        link = box_score_cell.find("a")["href"]
        game_id = link.split("/")[-1].replace(".html", "")
        games.append(
            Game(
                game_id=game_id,
                team_code=team_code,
                date=row.find("td", {"data-stat": "date_game"}).get_text(),
                opponent=row.find("td", {"data-stat": "opp_name"}).get_text(),
            )
        )
    return games


# Data Analysis

# ---------------------------------------------------------------------------
# Cache Check / Retrieval
# ---------------------------------------------------------------------------


def normalize_team_code(team):
    """Normalize full team name or 3-letter code to canonical code."""
    if not team:
        raise ValueError("team must be provided")
    s = str(team).strip()
    if len(s) == 3 and s.upper() in TEAM_TO_CODE.values():
        return s.upper()
    for name, code in TEAM_TO_CODE.items():
        if s.lower() == name.lower():
            return code
    raise ValueError(f"Unknown team: {team}")


def normalize_year(year):
    try:
        return int(year)
    except Exception:
        raise ValueError(f"Invalid year: {year}")


def get_cached_schedule(team_code, year):
    """Return list of :class:`Game` objects if schedule rows are cached.

    The NBA season spans two calendar years (e.g. the 2026 season includes
    games played in October–December 2025), so when requesting a schedule for
    *year* we look for games whose identifiers start with either that year or
    the preceding one.  The scraping code itself pulls the full season page
    which already contains both halves; the filter here simply ensures the
    cached query returns everything relevant to the requested season.

    Args:
        team_code: full team name or three-letter code (normalization applied)
        year: integer season year

    Returns:
        list of :class:`Game`.  Empty list if there is no data.
    """
    team_code = normalize_team_code(team_code)
    year = normalize_year(year)
    prefix1 = f"{year-1:04d}%"
    prefix2 = f"{year:04d}%"
    with sqlite3.connect(SCHEDULE_DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM team_schedule WHERE team_code = ? AND (game_id LIKE ? OR game_id LIKE ?)",
            (team_code, prefix1, prefix2),
        ).fetchall()
        return [Game(**dict(r)) for r in rows]


def get_cached_season(team_code, year):
    """Return list of :class:`SeasonPlayerStats` for a team/year if cached."""
    team_code = normalize_team_code(team_code)
    year = normalize_year(year)
    with sqlite3.connect(SEASON_STATS_DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM season_performances WHERE team = ? AND year = ?",
            (team_code, year),
        ).fetchall()
        return [SeasonPlayerStats(**dict(r)) for r in rows]


def get_cached_game(game_id):
    """Return player statistics for ``game_id`` if already in the database.

    Returns a list of :class:`PlayerGamePerformance` objects or an empty list.
    """
    with sqlite3.connect(STATS_DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM player_performances WHERE game_id = ?",
            (game_id,),
        ).fetchall()
        return [PlayerGamePerformance(**dict(r)) for r in rows]


def run_schedule_scraper(team_code, year):
    """Fetch a team's schedule for ``year``.

    The function is cache‑first: if rows exist in the schedule database they are
    returned directly, otherwise the page is fetched, parsed, stored, and then
    returned.

    Args:
        team_code: full team name or three-letter code (normalization applied)
        year: integer season year

    Returns:
        ``List[Game]`` describing the games for the team in that season.  The
        same list is also persisted in the schedule database.
    """
    init_all_dbs()
    team_code = normalize_team_code(team_code)
    year = normalize_year(year)

    cached = get_cached_schedule(team_code, year)
    if cached:
        print(f"Using cached schedule for {team_code} {year}")
        return cached

    url = f"https://www.basketball-reference.com/teams/{team_code}/{year}_games.html"
    html = guarded_fetch(url)
    games = parse_team_schedule(html, team_code)
    if games:
        save_schedule_to_db(games)
    return games


def run_season_scraper(team_code, year):
    """Fetch and cache per-game season averages for a team/year.

    The result is returned as a list of :class:`SeasonPlayerStats` objects.
    """
    init_all_dbs()
    team_code = normalize_team_code(team_code)
    year = normalize_year(year)

    cached = get_cached_season(team_code, year)
    if cached:
        print(f"Using cached season stats for {team_code} {year}")
        return cached

    url = f"https://www.basketball-reference.com/teams/{team_code}/{year}.html"
    html = guarded_fetch(url)
    stats = parse_team_season(html, team_code, year)
    if stats:
        save_season_to_db(stats)
    return stats


def season_year_for_game(game_id: str) -> int:
    """Return the canonical season year for a given *game_id*.

    The first four digits of the id are the calendar year; games played in
    October–December belong to the following season.  This helper encapsulates
    that logic so callers don’t accidentally use the wrong year when looking up
    averages.
    """
    cal_year = int(game_id[:4])
    month = int(game_id[4:6])
    # any month from October (10) through December (12) is treated as the next
    # season; everything else stays in the same year.
    if month >= 10:
        return cal_year + 1
    return cal_year


def run_game_scraper(game_id, year=None):
    """Fetch box-score statistics for a given game and ensure its season data
    are available.

    ``year`` should normally be the season year (e.g. 2026 for a game played
    in November 2025).  If omitted the value will be derived from ``game_id``
    using :func:`season_year_for_game`.

    If the *game_id* is already cached the existing rows are returned, and
    the function also verifies that season averages for all teams in the game
    exist, fetching them if necessary.

    Returns a list of :class:`PlayerGamePerformance` objects.
    """
    init_all_dbs()
    if year is None:
        year = season_year_for_game(game_id)
    year = normalize_year(year)

    cached_game = get_cached_game(game_id)
    if cached_game:
        print(f"Using cached player stats for game {game_id}")
        # Ensure season stats are present for all teams in the game
        teams = list({r.team for r in cached_game})
        for team_code in teams:
            if not get_cached_season(team_code, year):
                run_season_scraper(team_code, year)
        return cached_game

    url = f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    html = guarded_fetch(url)
    player_stats = parse_box_score(html, game_id)
    if not player_stats:
        return []

    save_to_db(player_stats)

    teams_in_game = list({p.team for p in player_stats})
    for team_code in teams_in_game:
        run_season_scraper(team_code, year)

    return player_stats


def get_stat_outliers(game_id, year, stats_to_track=["pts", "trb", "ast", "fg3"]):
    """Compute how individual game statistics compare to season averages.

    The caller can supply any subset of stats to evaluate.  For example,
    passing ``stats_to_track=["pts"]`` will restrict the result to point
    comparisons only (useful when you only care about scoring outliers).

    Args:
        game_id: identifier of the game to analyze
        year: season year used when looking up averages
        stats_to_track: list of field names (corresponding to columns in the
            databases) to compute percentages for.  Defaults to a handful of
            common rate stats.

    Returns:
        ``List[StatOutlier]`` sorted by descending percentage (largest
        outlier first).  An empty list means either the game wasn't cached or
        no matching season data was found.
    """
    # leverage the cache helper so we get dataclass objects directly
    game_data = get_cached_game(game_id)
    if not game_data:
        return []

    player_names = [p.player_name for p in game_data]
    placeholders = ", ".join(["?" for _ in player_names])
    with sqlite3.connect(SEASON_STATS_DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM season_performances WHERE year = ? AND player_name IN ({placeholders})",
            [year] + player_names,
        )
        season_map = {r["player_name"]: dict(r) for r in rows}

    all_performances = []
    for p_game in game_data:
        name = p_game.player_name
        if name not in season_map:
            continue
        for stat in stats_to_track:
            g_val = float(getattr(p_game, stat, 0) or 0)
            s_val = float(season_map[name].get(stat) or 0)
            pct = (g_val / s_val * 100) if s_val > 0 else 0
            all_performances.append(
                StatOutlier(name=name, stat=stat.upper(), val=g_val, avg=s_val, pct=pct)
            )

    return sorted(all_performances, key=lambda x: x.pct, reverse=True)


if __name__ == "__main__":
    # Example usage of the scraping/analysis system.

    # 1. ensure a team's season averages are cached
    run_season_scraper("WAS", 2026)

    # 2. grab (and cache) the schedule for the team
    schedule = run_schedule_scraper("WAS", 2026)
    print(f"Retrieved {len(schedule)} games for WAS 2026")

    # 3. pick a specific game from the schedule and compare stats
    if schedule:
        # sample_game = schedule[0]  # first game as a simple example
        # print(
        #     f"Inspecting game {sample_game.game_id} vs {sample_game.opponent} on {sample_game.date}"
        # )

        # fetch the box-score stats (cached if already pulled earlier)
        game_stats = run_game_scraper("202511250WAS", 2026)
        print(f"Retrieved {len(game_stats)} player performances for game 202511250WAS")

        # compute outliers relative to season averages
        outliers = get_stat_outliers("202511250WAS", 2026, ["fg3"])
        print("Top 5 outliers by percentage:")
        for o in outliers[:5]:
            print(f"  {o.name} {o.stat} {o.val}/{o.avg} ({o.pct:.1f}%)")
    else:
        print("Schedule was empty, nothing to inspect.")
