### Goals:

I want to practice using simple tools like beautifulsoup, matplotlib, and tkinter in a simple and expandable project.

I want to know what were the best performances I've seen from the NBA games I've been to. Outliers in performance are particularly of interest to me, for fun.

### Current TO-DO:

#### Stage 1: Backend

0. Create a github repo and gitignore for version control
1. Design functions to limit rate of calls per minute to prevent getting blocked for the day
2. Design network functions to retrieve data of teams' schedules by year, individual games, and season averages (done)
3. Design parsing functions to parse those data tables into 3 different sqlite databases
4. Design functions to interact with the individual game datatable: allowing filtering of players and stats, display the outlier games (relative to season avgs)
5. Consider sorting these functions into different sections or files for readability

#### Stage 2: Frontend

1. Design a tab to navigate between finding games, looking at stats, and app settings
2. Design frontend interface to find games: by date OR by team -> schedule
3. Design button to save a game to the database, making sure to clear the database of games you didn't explicitly save (so you can keep track of the ones you care about)
4. Design an interface for the individual game filtering and sorting

#### Stage 3: Wrap-up

1. Turn the project into an executable
2. Create a requirements.txt file if needed (?)
3. Create a README.md with instructions on how to use
4. Make the repo public

#### Stage 4: Additional Ideas

pick one for cache storage:

1. remove from cache when it's removed from the list
2. have some hard limit where it starts kicking out something so it doesn't get infinitely largest
   technically size isn't really an issue, its such a small amount of info i can't imagine itll matter.
