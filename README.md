# fantasy-football-lineup

fantasy-football-lineup is a tool to find the optimal lineup for manager games.

It was used for:

- [EURO 2020 Fantasy Football manager game](https://gaming.uefa.com/de/uefaeuro2020fantasyfootball)
- [Kicker Managerspiel Interactive Bundesliga 2023/24](https://www.kicker.de/managerspiel/interactive/se-k00012023)
- [Kicker Managerspiel Interactive EM 2024](https://www.kicker.de/managerspiel/interactive/se-k01072024)

## Usage example

```bash
> pip install -r requirements.txt
> python obtain_data.py
> python choose_team.py
+---------------------+------------------------+-----------------------+-----------------------+-------------------------+
|       Position      |          Name          | Ingame value [Mio. €] | Market value [Mio. €] | Ratio (market / ingame) |
+---------------------+------------------------+-----------------------+-----------------------+-------------------------+
| Position.GOALKEEPER |  Gianluigi Donnarumma  |          5.5          |          60.0         |          10.91          |
| Position.GOALKEEPER |    Thibaut Courtois    |          6.0          |          60.0         |          10.00          |
|   Position.DEFENSE  |   Alessandro Bastoni   |          4.5          |          60.0         |          13.33          |
|   Position.DEFENSE  |    Andrew Robertson    |          5.5          |          65.0         |          11.82          |
|   Position.DEFENSE  |    Matthijs de Ligt    |          5.5          |          75.0         |          13.64          |
|   Position.DEFENSE  |     Raphaël Varane     |          6.0          |          70.0         |          11.67          |
|   Position.DEFENSE  | Trent Alexander-Arnold |          6.5          |          75.0         |          11.54          |
|  Position.MIDFIELD  |    Frenkie de Jong     |          7.0          |          90.0         |          12.86          |
|  Position.MIDFIELD  |     Joshua Kimmich     |          6.0          |          90.0         |          15.00          |
|  Position.MIDFIELD  |     Leon Goretzka      |          6.5          |          70.0         |          10.77          |
|  Position.MIDFIELD  |    Marcos Llorente     |          5.0          |          70.0         |          14.00          |
|  Position.MIDFIELD  |         Rodri          |          5.0          |          70.0         |          14.00          |
|   Position.OFFENSE  |       Harry Kane       |          11.5         |         120.0         |          10.43          |
|   Position.OFFENSE  |     Kylian Mbappé      |          12.0         |         160.0         |          13.33          |
|   Position.OFFENSE  |    Mikel Oyarzabal     |          7.5          |          70.0         |           9.33          |
|          -          |         Total          |         100.0         |         1205.0        |          12.05          |
+---------------------+------------------------+-----------------------+-----------------------+-------------------------+
```

This example team is not based on the latest data. To get the best team, you should try yourself ;)

For extended usage, check the help of `obtain_data.py`. There are some useful flags for printing the players with the highest market to ingame value ratio, excluding players and refreshing the cache.

## Detailed workflow

| Step | Modules |
| --- | --- |
| Parse available players from <https://gaming.uefa.com/de/uefaeuro2020fantasyfootball> | [Selenium](https://www.selenium.dev/), because player list needs to be scrolled down |
| Parse market values from <https://www.transfermarkt.de> | [Beautifulsoup](https://www.crummy.com/software/BeautifulSoup/) |
| Match available players and their market values via player names | |
| Cache the data | Pickle (intermediate data), csv (completed player list) |
| Find 15 players with the highest market value, who still fit in the budget and in the formation | [Pyomo](https://www.pyomo.org/), [Pandas](https://pandas.pydata.org/) |
| Print the chosen players | [Prettytable](https://github.com/jazzband/prettytable) |

## Potential improvements

Consider more metrics than just the market value. The players with highest market values aren't guaranteed to play. Possible metrics:

- Ratings of the last year (club and national team)
- Appearances in the national team in the last year
- Bonus for penalty shooters

The metrics should be obtainable without many requests. Preferably team wise or even in a single database.

A known issue is that the script can't resolve duplicated names. Duplicated means the first letter of the first name and family name are identical. This could be fixed only with an ID system.

## Further links

This blog post inspired me to write these scripts: <https://thedatabarista.wordpress.com/2015/01/27/pyomo-meets-fantasy-football/>.
