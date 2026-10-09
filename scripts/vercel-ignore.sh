#!/usr/bin/env bash
# Vercel's Ignored Build Step (decision 0017): exit 0 skips the build, any other exit builds.
# Only main builds, and only when something the site is built from changed: data never rebuilds the site.
if [ "$VERCEL_GIT_COMMIT_REF" != "main" ]; then echo "previews are off (decision 0017)"; exit 0; fi
if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ]; then exit 1; fi
# data/ holds the sweep's inputs; the build reads only data/categories.csv (scripts/gen-categories.mjs). Until 9 Oct a
# blocklist change in data/ rebuilt the whole site (8 Oct 14:40, a full corpus-free build for a worker-only change).
if git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" HEAD -- . ':(exclude)worker' ':(exclude)ops' ':(exclude)supabase' \
     ':(exclude)docs' ':(exclude)decisions' ':(exclude)deploy' ':(exclude)*.md' ':(exclude)tests' ':(exclude)data' \
   && git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" HEAD -- data/categories.csv; then
  echo "no site change: data never rebuilds the site (decision 0017)"; exit 0
fi
exit 1
