# The daily fetch worker (Railway cron). Fetch + resolve + store only —
# classification and scoring run on the Mac, where the LLM engines live.
FROM python:3.12-slim

RUN pip install --no-cache-dir "psycopg[binary]" pyahocorasick

WORKDIR /app
COPY worker/ /app/worker/
# EVERY input the resolver reads must be here. Two of them were not, and the
# container quietly resolved against a different gazetteer than the Mac:
#   alias-blocklist.csv — 41 pairs the entity gate already rejected
#                         (aws→amazon-route-53, app→astro-pixel-processor…)
#   english-words.txt   — the plain-word guard; slim images have no
#                         /usr/share/dict/words, so 31 aliases resolved bare
# resolve.py now raises when either is absent rather than changing behaviour.
COPY data/categories.csv data/category-subreddits.csv data/brands.csv \
     data/brand-aliases.csv data/alias-blocklist.csv data/english-words.txt \
     /app/data/

# Fail the BUILD, not a 02:00 cron, if the gazetteer the image carries is not
# the gazetteer the code expects.
RUN python3 -c "import sys; sys.path.insert(0,'/app/worker'); import resolve; \
    assert len(resolve._BLOCKED) >= 40, resolve._BLOCKED; \
    assert len(resolve._ENGLISH) > 200000, len(resolve._ENGLISH); \
    print('gazetteer parity ok:', len(resolve._BLOCKED), 'blocked,', \
          len(resolve._ENGLISH), 'words')"

ENV RI_CACHE=/tmp/ri-cache
CMD ["python3", "-u", "/app/worker/daily.py"]
