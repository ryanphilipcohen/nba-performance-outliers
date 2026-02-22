1. **Schedule scraper** – input is a team (full name or 3‑letter code)
   and a season year. The implementation normalizes the inputs and checks the
   `nba_schedules.db` cache. If cached rows exist it returns a list of
   `Game` dataclasses; otherwise it fetches the
   `/teams/{TEAM}/{YEAR}_games.html` page, passes the raw HTML to
   `parse_team_schedule` which builds the dataclasses, persists the list, and
   returns it. An empty list means the page could not be found or parsed.

2. **Season stats scraper** – similar to the schedule scraper but operates on
   the team/year landing page and returns `SeasonPlayerStats` objects that
   are stored in `nba_season_totals.db`.

3. **Box‑score scraper** – given a `game_id` and year the code first
   attempts to load cached player performances from `nba_stats.db`; these are
   provided as `PlayerGamePerformance` dataclasses. If the game isn’t
   cached the scraper downloads the box score, extracts each player as a
   dataclass, inserts the results into the database, and makes sure the
   relevant season averages exist for each team in the game before returning
   the list.

4. **Outlier analysis** – `get_stat_outliers(game_id, year)` combines the
   cached game and season data and computes a percentage for each tracked stat
   versus the season average. It yields a sorted list of `StatOutlier`
   dataclasses; the fields include the raw value, average, and percentage.  A
   custom set of stats may be specified (e.g. ``["pts"]`` for points only) and
   a small wrapper ``get_points_outliers`` is provided.

   _Potential future helper functions:_
   * delete a single game or season entry from the cache
   * query schedule by date or opponent
   * summarize team totals/averages for a game
   * export results to CSV/JSON
   * simple CLI interface accepting command-line arguments
