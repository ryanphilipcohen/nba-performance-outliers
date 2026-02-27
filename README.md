# NBA Performance Outliers

A local Python app that helps you track NBA games you attended and find player performances that were outliers compared to season averages.

It includes:

- `main.py`: scraping, caching, and outlier analysis logic
- `frontend.py`: Tkinter GUI for loading schedules, tracking games, and viewing outliers

## Features

- Pulls team schedules by season from Basketball Reference
- Pulls single-game box score stats and season per-game averages
- Caches data in SQLite databases to avoid repeated network calls
- Computes outliers (example: points, rebounds, assists, 3PM) as `% of season average`
- GUI to:
  - load team schedules
  - add/remove tracked games
  - view and sort outliers
  - choose which stats are considered in outlier calculations

## Project Structure

- `frontend.py` - Tkinter desktop UI
- `main.py` - backend scraping/parsing/storage/analysis functions
- `goals.md` - project goals and TODOs
- `rate_limiter.db` - API request window tracking
- `nba_schedules.db` - cached team schedules
- `nba_stats.db` - cached player game box-score stats
- `nba_season_totals.db` - cached season per-game stats
- `tracked_games.json` - persisted tracked games list (created automatically)

Python packages used:

- `requests`
- `beautifulsoup4`
- `tkinter` (included with most standard Python installs on Windows)

## Setup

1. Clone the repo.
2. (Recommended) Create and activate a virtual environment.
3. Install dependencies:

```powershell
pip install requests beautifulsoup4
```

## Usage

Run the GUI:

```powershell
python frontend.py
```

### GUI workflow

1. Open **Seasons** tab.
2. Select a team and enter a season year.
   - Example: `2026` means the **2025-26** NBA season.
3. Click **Load Schedule**.
4. Select a game and click **Add to tracked**.
5. Open **Outliers** tab.
6. Check one or more tracked games and click **Refresh**.
7. Sort by `pct`, `val`, or other fields to inspect top outlier performances.

### Backend usage (optional)

If you want to run analysis from scripts:

```python
from main import run_schedule_scraper, run_game_scraper, get_stat_outliers, season_year_for_game

schedule = run_schedule_scraper("WAS", 2026)
game_id = schedule[0].game_id
year = season_year_for_game(game_id)
run_game_scraper(game_id, year)
outliers = get_stat_outliers(game_id, year, ["pts", "trb", "ast", "fg3"])
print(outliers[:10])
```

## Data and Caching Notes

- Data is cached in local SQLite DB files in the project root.
- `tracked_games.json` is created automatically when you add tracked games in the GUI.
- To clear cached data, use helper functions in `main.py`:
  - `clear_stats_db()`
  - `clear_season_db()`
  - `clear_schedule_db()`
  - `clear_all_dbs()`

## Known Issue

Season overlap caching (for adjacent years like 2025 and 2026) can return incorrect schedule rows in some cases. You already noted this in `goals.md`; adding an explicit `season_year` column to schedule records is a good fix direction.

## TODO

check if you're still hitting the rate limits? (403)

Create venv and requirements.txt
integrate into readme
