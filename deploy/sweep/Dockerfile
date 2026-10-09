# The Reddit Index daily sweep (worker/run_daily.py) on its own Railway service, reddit-index-sweep.
# Built ONLY from the folder ops/deploy_sweep.py assembles, never from the repository root: the root's
# railway.json belongs to the parked collector service and must stay parked.

# The Codex CLI is the transport to GLM (the estate's rule: Z.ai's official route, never a custom client).
FROM node:22-bookworm-slim AS codex
RUN npm install -g @openai/codex@0.154.0

FROM python:3.12-slim-bookworm
COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
 && pip install --no-cache-dir "psycopg[binary]" pyahocorasick

WORKDIR /app
COPY worker/ /app/worker/
COPY data/ /app/data/
COPY ops/ /app/ops/
COPY api_helpers/ /app/api_helpers/
COPY codex-zai/ /app/codex-zai/

# Fail the BUILD, not a midnight run, if the image is missing something a stage reads.
# (placeholder Reddit values: the client refuses to import without them; the real ones are Railway variables)
RUN codex --version \
 && REDDIT_CLIENT_ID=build REDDIT_CLIENT_SECRET=build REDDIT_USER_AGENT=build python3 -c "import sys; sys.path.insert(0,'/app/worker'); import resolve, collect, takedown, classify_sweep, \
    site_score, site_publish, run_daily, sweep; assert run_daily.backfill_subs(['itsm'], '/app/data/category-subreddits.csv'); assert len(resolve._BLOCKED) >= 40; assert len(resolve._HOSTILE) >= 1; assert len(resolve._ENGLISH) > 200000; \
    import json; json.load(open('/app/ops/schedule.json')); json.load(open('/app/ops/classify_thresholds.json')); \
    print('sweep image ok')"

ENV RI_CACHE=/tmp/ri-cache \
    RI_API_HELPERS=/app/api_helpers \
    CODEX_HOME=/app/codex-zai \
    TYPESAFE_CACHE_DIR=/tmp/typesafe-cache \
    PYTHONUNBUFFERED=1
CMD ["python3", "-u", "/app/worker/run_daily.py"]
