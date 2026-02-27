# NBA Performance Outliers

Have I seen a bench player have a breakout game? Did a star player have a sneaky good rebounding game? What are the best performances I've seen at the NBA games I've been to?

This project is local Python desktop app using web scraping, a simple tkinter frontend, and sqlite3, for identifying standout NBA single-game performances from games you attended by comparing each player's box-score output to their season averages.

## Features

- Pulls team schedules by season from Basketball Reference
- Pulls single-game box score stats and season per-game averages
- Computes outlier scores as a percentage of season average (example: `pts`, `trb`, `ast`, `fg3`)
- Caches schedules, box scores, and season averages in SQLite
- GUI workflow for:
  - loading schedules
  - tracking attended games
  - selecting which stats are included
  - sorting and reviewing top outliers

## Project Structure

- `frontend.py` - Tkinter app and user workflow
- `backend.py` - scraping, parsing, caching, and outlier script logic
- `.db` and `.json` files - generated for storing schedules, games, averages, and requests

## Data and Cache Behavior

- Caches are persisted locally in SQLite files in the project root.
- `tracked_games.json` is created automatically when you track games.
- You can clear cached data with helper functions in `main.py`:
  - `clear_stats_db()`
  - `clear_season_db()`
  - `clear_schedule_db()`
  - `clear_all_dbs()`

## Setup

1. Clone the repository.
2. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

For macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

## Running the App

```powershell
python frontend.py
```

## Typical Workflow

1. Open the **Seasons** tab.
2. Select a team and enter season year.
3. Click **Load Schedule**.
4. Add one or more games to tracked games.
5. Open **Outliers** tab.
6. Select tracked games and click **Refresh**.
7. Sort by `%`, `value`, or `avg` categories to inspect top performers or outliers relative to season averages.

## Rate Limiting and Data Source Notes

The app currently scrapes Basketball Reference pages, so request pacing matters.

- Internal limiter is set to `19 requests / 60 seconds` (`MAX_CALLS=19`, `WINDOW_SIZE=60`) in `main.py`.

Sports Reference bot/rate-limit policy:

- https://www.sports-reference.com/bot-traffic.html

If you are blocked, wait for the cooldown window and try again later.

## Known Issue

Temporary rate-related scraping bans may occur despite the rate limiter. Cause of issue is unknown.

## Future Plans

- Add export options (CSV/JSON) for outlier results
- Improve location/config management for DB and JSON files
- Add richer stat filters and presets in the UI
- Create graphics for visualization and special easy-to-read exports
