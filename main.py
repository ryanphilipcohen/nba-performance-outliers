import requests
import sqlite3
import time
from bs4 import BeautifulSoup

RL_DB_NAME = "rate_limiter.db"
STATS_DB_NAME = "nba_stats.db"
MAX_CALLS = 19  # per https://www.sports-reference.com/bot-traffic.html
WINDOW_SIZE = 60  # Seconds

# Rate Limiter


def init_rl_db():
    """Initialize the database that tracks request timestamps."""
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS api_calls (timestamp REAL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON api_calls(timestamp)")


def get_current_window_count():
    """Count how many requests were made in the last 60 seconds."""
    now = time.time()
    cutoff = now - WINDOW_SIZE
    with sqlite3.connect(RL_DB_NAME) as conn:
        # Clean up old timestamps to keep the DB light
        conn.execute("DELETE FROM api_calls WHERE timestamp < ?", (cutoff,))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM api_calls WHERE timestamp >= ?", (cutoff,)
        )
        return cursor.fetchone()[0]


def log_call():
    """Record the timestamp of a successful request."""
    with sqlite3.connect(RL_DB_NAME) as conn:
        conn.execute("INSERT INTO api_calls (timestamp) VALUES (?)", (time.time(),))


# Network Calls


def guarded_fetch(url):
    """Fetches HTML only if within rate limits. Otherwise, waits."""
    while True:
        count = get_current_window_count()
        if count < MAX_CALLS:
            log_call()
            print(f"Requesting: {url} (Window count: {count + 1})")
            response = requests.get(url)

            if response.status_code == 429:
                print("Hit 429 (Rate Limit)! Sleeping for 30s...")
                time.sleep(30)
                continue

            return response.text
        else:
            print(f"Limit reached ({count}/{MAX_CALLS}). Waiting 5s...")
            time.sleep(5)


# Parsing


def extract_player_stats(row, game_id, team_code):
    """Parses a single HTML table row into a dictionary."""
    # Skip header rows often found mid-table (e.g., 'Reserves')
    if row.get("class") and "thead" in row.get("class"):
        return None

    # Player name is stored in 'th', stats in 'td'
    name_cell = row.find("th", {"data-stat": "player"})
    if not name_cell:
        return None

    p = {"game_id": game_id, "team": team_code, "player_name": name_cell.get_text()}

    # Map the remaining stat columns
    for td in row.find_all("td"):
        stat_name = td.get("data-stat")
        p[stat_name] = td.get_text()

    return p


def parse_box_score(html_content, game_id):
    """Loops through tables in the HTML to find player stats."""
    soup = BeautifulSoup(html_content, "html.parser")
    all_players = []

    # Basketball Reference uses specific IDs for basic box score tables
    tables = soup.find_all("table", id=lambda x: x and x.endswith("-game-basic"))

    for table in tables:
        try:
            # Extract 'WAS' from 'box-WAS-game-basic'
            team_code = table.get("id").split("-")[1]
            rows = table.find("tbody").find_all("tr")

            for row in rows:
                player_data = extract_player_stats(row, game_id, team_code)
                if player_data:
                    all_players.append(player_data)
        except (IndexError, AttributeError):
            continue

    return all_players


# Storage


def init_stats_db():
    """Creates the data table if it doesn't exist."""
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


def save_to_db(data_list):
    """Adds the list of player dictionaries into the stats database."""
    if not data_list:
        return

    # Pick out which columns I care about
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
    col_string = ", ".join(columns)

    query = f"INSERT OR REPLACE INTO player_performances ({col_string}) VALUES ({placeholders})"

    with sqlite3.connect(STATS_DB_NAME) as conn:
        # Prepare the list of tuples for executemany
        rows_to_insert = [tuple(d.get(col) for col in columns) for d in data_list]
        conn.executemany(query, rows_to_insert)
        conn.commit()


# Condensed Functions


def run_scraper(url):
    """Main execution flow for a single URL."""
    # Setup
    init_rl_db()
    init_stats_db()
    game_id = url.split("/")[-1].replace(".html", "")

    # Fetch
    html = guarded_fetch(url)

    # Parse
    player_stats = parse_box_score(html, game_id)

    # Save
    if player_stats:
        save_to_db(player_stats)
        print(f"Successfully saved {len(player_stats)} player records for {game_id}.")
    else:
        print(
            f"No data found for {game_id}. (You should check the URL or HTML structure.)"
        )


# Example Execution
if __name__ == "__main__":
    test_url = "https://www.basketball-reference.com/boxscores/202511250WAS.html"
    run_scraper(test_url)
