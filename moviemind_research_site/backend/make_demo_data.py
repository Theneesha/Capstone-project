"""Creates a small DEMO dataset (data/movies.csv, data/ratings.txt) so the app runs out of the box.
Replace both files with your real MovieLens-format files (10,329 movies / 105,339 ratings) for the real run.
Formats accepted: movies.csv = movieId,title,genres ; ratings.txt = userId,movieId,rating,timestamp (CSV, TSV or '::')."""
import numpy as np, pandas as pd, os
from core import GENRES
rng = np.random.default_rng(7)
titles = """Toy Story (1995)|Adventure|Animation|Children|Comedy|Fantasy
Jumanji (1995)|Adventure|Children|Fantasy
Heat (1995)|Action|Crime|Thriller
Se7en (1995)|Mystery|Thriller
Braveheart (1995)|Action|Drama|War
Apollo 13 (1995)|Adventure|Drama|IMAX
Casino (1995)|Crime|Drama
Pulp Fiction (1994)|Comedy|Crime|Drama|Thriller
The Lion King (1994)|Adventure|Animation|Children|Drama|Musical|IMAX
Forrest Gump (1994)|Comedy|Drama|Romance|War
The Shawshank Redemption (1994)|Crime|Drama
Speed (1994)|Action|Romance|Thriller
Dumb & Dumber (1994)|Adventure|Comedy
Léon: The Professional (1994)|Action|Crime|Drama|Thriller
Schindler's List (1993)|Drama|War
Jurassic Park (1993)|Action|Adventure|Sci-Fi|Thriller
Groundhog Day (1993)|Comedy|Fantasy|Romance
The Fugitive (1993)|Thriller
Aladdin (1992)|Adventure|Animation|Children|Comedy|Musical
Unforgiven (1992)|Western
Reservoir Dogs (1992)|Crime|Mystery|Thriller
Terminator 2 (1991)|Action|Sci-Fi
The Silence of the Lambs (1991)|Crime|Horror|Thriller
Beauty and the Beast (1991)|Animation|Children|Fantasy|Musical|Romance|IMAX
Goodfellas (1990)|Crime|Drama
Home Alone (1990)|Children|Comedy
Dances with Wolves (1990)|Adventure|Drama|Western
Back to the Future (1985)|Adventure|Comedy|Sci-Fi
Aliens (1986)|Action|Adventure|Horror|Sci-Fi
Top Gun (1986)|Action|Romance
Platoon (1986)|Drama|War
Blade Runner (1982)|Action|Sci-Fi|Thriller
E.T. the Extra-Terrestrial (1982)|Children|Drama|Sci-Fi
The Thing (1982)|Action|Horror|Mystery|Sci-Fi|Thriller
Raiders of the Lost Ark (1981)|Action|Adventure
The Shining (1980)|Horror
Star Wars: Episode V (1980)|Action|Adventure|Sci-Fi
Alien (1979)|Horror|Sci-Fi
Apocalypse Now (1979)|Action|Drama|War
The Godfather (1972)|Crime|Drama
Chinatown (1974)|Crime|Film-Noir|Mystery|Thriller
The Maltese Falcon (1941)|Film-Noir|Mystery
Double Indemnity (1944)|Crime|Drama|Film-Noir
The Big Sleep (1946)|Crime|Film-Noir|Mystery
Casablanca (1942)|Drama|Romance
The Sound of Music (1965)|Musical|Romance
West Side Story (1961)|Drama|Musical|Romance
Singin' in the Rain (1952)|Comedy|Musical|Romance
The Good, the Bad and the Ugly (1966)|Action|Adventure|Western
High Noon (1952)|Drama|Western
Bowling for Columbine (2002)|Documentary
March of the Penguins (2005)|Documentary
Super Size Me (2004)|Documentary
Spirited Away (2001)|Adventure|Animation|Fantasy
Finding Nemo (2003)|Adventure|Animation|Children|Comedy
Shrek (2001)|Adventure|Animation|Children|Comedy|Fantasy|Romance
The Matrix (1999)|Action|Sci-Fi|Thriller
Gladiator (2000)|Action|Adventure|Drama
Titanic (1997)|Drama|Romance
Fargo (1996)|Comedy|Crime|Drama|Thriller
The Sixth Sense (1999)|Drama|Mystery|Thriller
Inception (2010)|Action|Crime|Drama|Mystery|Sci-Fi|Thriller|IMAX
The Dark Knight (2008)|Action|Crime|Drama|IMAX
Mad Max: Fury Road (2015)|Action|Adventure|Sci-Fi|Thriller
La La Land (2016)|Comedy|Drama|Musical|Romance
Get Out (2017)|Horror|Mystery|Thriller
Saving Private Ryan (1998)|Action|Drama|War
Life Is Beautiful (1997)|Comedy|Drama|Romance|War
Amelie (2001)|Comedy|Romance
Coco (2017)|Adventure|Animation|Children|Fantasy|Musical
Interstellar (2014)|Sci-Fi|IMAX
Parasite (2019)|Comedy|Crime|Drama|Thriller""".split("\n")
rows = [(i + 1, *(t.split("|")[0], "|".join(t.split("|")[1:]))) for i, t in enumerate(titles)]
# add synthetic filler titles so every genre is represented and the catalogue has some depth
for k in range(len(rows) + 1, 241):
    g = list(rng.choice(GENRES, size=rng.integers(1, 4), replace=False))
    rows.append((k, f"Demo Feature {k} ({rng.integers(1960, 2020)})", "|".join(g)))
movies = pd.DataFrame(rows, columns=["movieId", "title", "genres"])
G = np.zeros((len(movies), len(GENRES)))
for i, g in enumerate(movies.genres):
    for x in g.split("|"): G[i, GENRES.index(x)] = 1
quality = rng.normal(0, .5, len(movies)); pop = rng.pareto(1.2, len(movies)) + 1; pop /= pop.sum()
out = []
for u in range(1, 201):
    pref = rng.dirichlet(np.full(len(GENRES), .4)) * len(GENRES)
    n = int(rng.integers(25, 90))
    for i in rng.choice(len(movies), n, replace=False, p=pop):
        aff = (G[i] @ pref) / max(G[i].sum(), 1)
        r = np.clip(round(3 + (aff - 1) * 1.2 + quality[i] + rng.normal(0, .6)), 1, 5)
        out.append((u, int(movies.movieId[i]), int(r), 1_300_000_000 + int(rng.integers(0, 1e8))))
os.makedirs("data", exist_ok=True)
movies.to_csv("data/movies.csv", index=False)
pd.DataFrame(out, columns=["userId", "movieId", "rating", "timestamp"]).to_csv("data/ratings.txt", index=False)
print(len(movies), "movies,", len(out), "ratings,", 200, "users written to data/")
