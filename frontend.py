"""Simple tkinter GUI frontend for nba-performance-outliers

This module provides a basic interface on top of the scraping/analysis
functions defined in :mod:`main`.  It exposes three panels:

1. **Seasons** – choose a team and a season year (e.g. enter 2026 to
   fetch the 2025‑26 slate, which includes games played in late 2025), load
   the schedule and optionally add games to a tracked list.
2. **Outliers** – browse the games you have added, inspect individual or
   multiple games for statistical outliers, and sort by different metrics.
3. **Settings** – adjust a few configuration options (currently just the
   list of stats that the outlier engine considers).

The GUI is intentionally lightweight; it uses ``tkinter`` since no external
dependencies are required.  It stores the list of tracked games in memory
for the duration of the session and also persists them to ``tracked_games.json``
so that your selection survives restarts.  When you switch to the Outliers
panel the same tracked list appears there; select one or more games and
click *Refresh* to compute the statistical outliers.  (The persistence layer
could be swapped for a database or other storage later.)

Usage::

    python frontend.py

"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict

from main import (
    TEAM_TO_CODE,
    run_schedule_scraper,
    run_game_scraper,
    run_season_scraper,
    get_stat_outliers,
    season_year_for_game,
)

# ---------------------------------------------------------------------------
# helper data structures
# ---------------------------------------------------------------------------

import json
import os

TrackedGames: List[Dict] = []  # each entry is a schedule Game-like dict
TRACKED_FILE = "tracked_games.json"
checked_game_vars: List[tuple] = []

# default stats to compute outliers for; editable in settings pane
STATS_TO_TRACK = ["pts", "trb", "ast"]


# persistence helpers -------------------------------------------------------


def save_tracked_games():
    """Write the current tracked list to disk."""
    try:
        with open(TRACKED_FILE, "w") as f:
            json.dump(TrackedGames, f)
    except Exception:
        # ignore failures, file is just convenience
        pass


def load_tracked_games():
    """Read the list of tracked games from disk if present."""
    if not os.path.exists(TRACKED_FILE):
        return
    try:
        with open(TRACKED_FILE) as f:
            data = json.load(f)
        if isinstance(data, list):
            TrackedGames.clear()
            TrackedGames.extend(data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GUI callbacks and helpers
# ---------------------------------------------------------------------------


def load_schedule():
    """Fetch schedule for the selected team/year and display it."""
    team = team_var.get()
    year = year_var.get().strip()
    if not team or not year:
        return
    code = TEAM_TO_CODE.get(team)
    try:
        year_int = int(year)
    except ValueError:
        messagebox.showerror("Invalid year", "Year must be an integer")
        return

    # use the scraping helper which will cache as needed
    try:
        schedule = run_schedule_scraper(code, year_int)
    except Exception as exc:
        messagebox.showerror(
            "Schedule load failed",
            f"Could not load schedule for {team} {year_int}.\n\n{exc}",
        )
        return
    schedule_listbox.delete(0, tk.END)
    for game in schedule:
        schedule_listbox.insert(
            tk.END, f"{game.date} vs {game.opponent} ({game.game_id})"
        )
    if not schedule:
        messagebox.showwarning(
            "No schedule rows found",
            "No games were parsed for that team/year. Try again or choose another season.",
        )

    # store list for later lookup
    load_schedule.games = schedule


def add_selected_game():
    """Add the currently highlighted schedule entry to tracked list."""
    sel = schedule_listbox.curselection()
    if not sel:
        return
    idx = sel[0]
    game = load_schedule.games[idx]
    if any(g["game_id"] == game.game_id for g in TrackedGames):
        return  # already in list
    TrackedGames.append(
        {
            "game_id": game.game_id,
            "date": game.date,
            "opponent": game.opponent,
            "team": game.team_code,
        }
    )
    update_tracked_widgets()
    save_tracked_games()


def tracked_game_label(game: Dict) -> str:
    """Return a user-facing label for a tracked game."""
    return f"{game['date']} {game['team']} vs {game['opponent']}"


def populate_tracked_list():
    """(re)fill the tracked-games listbox from the in-memory store."""
    tracked_listbox.delete(0, tk.END)
    for g in TrackedGames:
        tracked_listbox.insert(tk.END, tracked_game_label(g))


def remove_games_by_ids(game_ids):
    """Remove all tracked games whose ids are in game_ids."""
    if not game_ids:
        return
    TrackedGames[:] = [g for g in TrackedGames if g["game_id"] not in set(game_ids)]
    update_tracked_widgets()
    save_tracked_games()


def remove_selected_games():
    """Remove selected games from the Seasons panel tracked list."""
    sel = tracked_listbox.curselection()
    if not sel:
        return
    ids = [TrackedGames[i]["game_id"] for i in sel]
    remove_games_by_ids(ids)


def build_outlier_checkboxes():
    """Rebuild the checkbox list used to select games in Outliers."""
    global checked_game_vars
    checked_game_vars = []
    for child in outlier_checks_inner.winfo_children():
        child.destroy()

    for game in TrackedGames:
        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(
            outlier_checks_inner,
            text=tracked_game_label(game),
            variable=var,
            command=lambda: root.after(10, show_outliers),
        )
        chk.pack(anchor=tk.W, fill=tk.X, padx=2, pady=1)
        checked_game_vars.append((game["game_id"], var))


def set_all_outlier_checks(value: bool):
    """Set all outlier game checkboxes to value and refresh."""
    for _, var in checked_game_vars:
        var.set(value)
    show_outliers()


def remove_checked_games():
    """Remove games checked in the Outliers panel."""
    ids = [gid for gid, var in checked_game_vars if var.get()]
    remove_games_by_ids(ids)


def update_tracked_widgets():
    """Refresh all widgets that display the tracked games."""
    populate_tracked_list()
    # if outliers widgets exist, update them as well
    try:
        build_outlier_checkboxes()
    except NameError:
        pass


def show_outliers():
    """Compute and display outliers for selected tracked game(s)."""
    game_ids = []
    try:
        game_ids = [gid for gid, var in checked_game_vars if var.get()]
    except NameError:
        pass
    # fall back to seasons tab selection if no games are checked in Outliers
    if not game_ids:
        sel = tracked_listbox.curselection()
        if sel:
            game_ids = [TrackedGames[i]["game_id"] for i in sel]
    if not game_ids:
        sel = tracked_listbox.curselection()
        # default to all tracked games if there are any
        if TrackedGames:
            game_ids = [g["game_id"] for g in TrackedGames]
        else:
            messagebox.showinfo("No games", "You haven't tracked any games yet.")
            return
    all_outliers = []
    for gid in game_ids:
        # ensure game statistics are available; this will also fetch seasons
        # as needed.  determine the correct season using the helper so that
        # early‑season (Oct–Dec) games map into the following year.
        year = season_year_for_game(gid)
        run_game_scraper(gid, year)
        outs = get_stat_outliers(gid, year, stats_to_track=STATS_TO_TRACK)
        for o in outs:
            all_outliers.append((gid, o))

    # clear tree
    for row in outlier_tree.get_children():
        outlier_tree.delete(row)

    # sort by selected metric
    metric = sort_var.get()
    if metric:
        all_outliers.sort(key=lambda tup: getattr(tup[1], metric, 0), reverse=True)

    for gid, o in all_outliers:
        outlier_tree.insert(
            "",
            tk.END,
            values=(
                gid,
                o.name,
                o.stat,
                o.val,
                o.avg,
                f"{o.pct:.1f}",
            ),
        )


def update_stats_to_track():
    """Refresh the list of stats from the settings panel."""
    global STATS_TO_TRACK
    STATS_TO_TRACK = []
    for chk, stat in zip(stat_checks, available_stats):
        if chk.var.get():
            STATS_TO_TRACK.append(stat)


# ---------------------------------------------------------------------------
# build the main window
# ---------------------------------------------------------------------------

root = tk.Tk()
root.title("NBA Performance Outliers")
root.geometry("800x600")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)


# automatically refresh outlier data whenever the Outliers tab is shown
def on_tab_change(event):
    tab = event.widget.tab(event.widget.select(), "text")
    if tab == "Outliers":
        show_outliers()


notebook.bind("<<NotebookTabChanged>>", on_tab_change)

# -- Seasons tab ------------------------------------------------------------
seasons_frame = ttk.Frame(notebook)
notebook.add(seasons_frame, text="Seasons")

team_var = tk.StringVar()
year_var = tk.StringVar()

controls = ttk.Frame(seasons_frame)
controls.pack(fill=tk.X, pady=5)

ttk.Label(controls, text="Team:").pack(side=tk.LEFT, padx=5)
team_combo = ttk.Combobox(controls, textvariable=team_var, width=30)
team_combo["values"] = list(TEAM_TO_CODE.keys())
team_combo.pack(side=tk.LEFT)

ttk.Label(controls, text="Season year (e.g. 2026 for 2025-26):").pack(
    side=tk.LEFT, padx=5
)
year_entry = ttk.Entry(controls, textvariable=year_var, width=6)
year_entry.pack(side=tk.LEFT)

ttk.Button(controls, text="Load Schedule", command=load_schedule).pack(
    side=tk.LEFT, padx=5
)

schedule_listbox = tk.Listbox(seasons_frame, height=15)
schedule_listbox.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)

add_button = ttk.Button(seasons_frame, text="Add to tracked", command=add_selected_game)
add_button.pack(pady=5)

# tracked list shown at bottom
tracked_label = ttk.Label(seasons_frame, text="Tracked games:")
tracked_label.pack()
tracked_listbox = tk.Listbox(seasons_frame, selectmode=tk.EXTENDED, height=8)
tracked_listbox.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)

tracked_buttons = ttk.Frame(seasons_frame)
tracked_buttons.pack(fill=tk.X, padx=5, pady=(0, 5))
ttk.Button(
    tracked_buttons,
    text="Remove selected",
    command=remove_selected_games,
).pack(side=tk.LEFT)

# load any previously saved tracked games and populate both lists
load_tracked_games()
update_tracked_widgets()

# -- Outliers tab ----------------------------------------------------------
outliers_frame = ttk.Frame(notebook)
notebook.add(outliers_frame, text="Outliers")

# tracked games shown in this panel as well; selecting filters the
# outliers immediately
ttk.Label(outliers_frame, text="Tracked games (check one or more to filter):").pack(
    anchor=tk.W, pady=(5, 0)
)

outlier_checks_outer = ttk.Frame(outliers_frame)
outlier_checks_outer.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
outlier_checks_inner = ttk.Frame(outlier_checks_outer)
outlier_checks_inner.pack(fill=tk.BOTH, expand=True)

outlier_check_controls = ttk.Frame(outliers_frame)
outlier_check_controls.pack(fill=tk.X, padx=5, pady=(0, 5))
ttk.Button(
    outlier_check_controls,
    text="Select all",
    command=lambda: set_all_outlier_checks(True),
).pack(side=tk.LEFT)
ttk.Button(
    outlier_check_controls,
    text="Clear checks",
    command=lambda: set_all_outlier_checks(False),
).pack(side=tk.LEFT, padx=5)
ttk.Button(
    outlier_check_controls, text="Remove checked", command=remove_checked_games
).pack(side=tk.LEFT)

# ensure the copy stays in sync when loading
update_tracked_widgets()

sort_var = tk.StringVar()

sort_controls = ttk.Frame(outliers_frame)
sort_controls.pack(fill=tk.X, pady=5)

ttk.Label(sort_controls, text="Sort by:").pack(side=tk.LEFT, padx=5)
sort_combo = ttk.Combobox(sort_controls, textvariable=sort_var, width=10)
sort_combo["values"] = ["stat", "val", "avg", "pct"]
sort_combo.pack(side=tk.LEFT)

ttk.Button(sort_controls, text="Refresh", command=show_outliers).pack(
    side=tk.LEFT, padx=5
)

cols = ("game_id", "player", "stat", "value", "avg", "%")
outlier_tree = ttk.Treeview(outliers_frame, columns=cols, show="headings")
for c in cols:
    outlier_tree.heading(c, text=c)
outlier_tree.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)

# -- Settings tab ----------------------------------------------------------
settings_frame = ttk.Frame(notebook)
notebook.add(settings_frame, text="Settings")

available_stats = ["pts", "trb", "ast", "fg3", "fg", "fga"]
stat_checks: List[ttk.Checkbutton] = []

setting_label = ttk.Label(settings_frame, text="Statistics to consider for outliers:")
setting_label.pack(anchor=tk.W, pady=5)

for stat in available_stats:
    var = tk.BooleanVar(value=(stat in STATS_TO_TRACK))
    chk = ttk.Checkbutton(
        settings_frame, text=stat, variable=var, command=update_stats_to_track
    )
    chk.var = var  # attach for later inspection
    chk.pack(anchor=tk.W)
    stat_checks.append(chk)

root.mainloop()
