# The daily fetch worker (Railway cron). Fetch + resolve + store only —
# classification and scoring run on the Mac, where the LLM engines live.
FROM python:3.12-slim

RUN pip install --no-cache-dir "psycopg[binary]" pyahocorasick

WORKDIR /app
COPY worker/ /app/worker/
COPY data/categories.csv data/category-subreddits.csv data/brands.csv data/brand-aliases.csv /app/data/

ENV RI_CACHE=/tmp/ri-cache
CMD ["python3", "-u", "/app/worker/daily.py"]
