#!/usr/bin/env python3
"""Sentiment for new mentions: Jev decides what it is sure of, GLM-Flash takes the rest.

Replaces the DeepSeek lane (worker/classify_api.py; DeepSeek is retired, doctrine G3). Shape, per the
estate's doctrine (jev-assistant, G19 to G29):

  * Jev (TypeSafe System One, pinned jev-1.13.0) answers two ORTHOGONAL questions per mention, twenty
    mentions a request: is the marked span this product at all (a yes/no probability), and how does the
    author feel about it (a distribution over positive / negative / no opinion / cannot tell). The old
    rubric was one chain of overriding clauses, the shape a verbatim port loses on; its rules are kept,
    word for word, as the guidance both questions read.
  * The precedence is arithmetic here, in code (decide()): a confident "not this product" is a rejection;
    a confident product AND a confident feeling is a label; everything else goes to GLM.
  * GLM-5.3 gets the residue with the old rubric verbatim, a hundred mentions a job, through the official
    Codex CLI on its own CODEX_HOME (G13), never at Z.ai's peak hours. GLM-5.3, not Flash: on the same 350
    mentions Flash called half the real opinions "no opinion" (read by hand, 2026-10-02); GLM-5.3 kept them.
  * Jev's thresholds were measured against GLM-5.3's own answers on 2,380 mentions, so a mention Jev settles
    gets the label GLM-5.3 would have given it 95.6% of the time (held out over twenty splits).
  * What neither judged is `not_checked`: it stays in the queue, is counted on the receipt, and is never
    scored, never written, never cached (G29).

Thresholds come from ops/classify_calibrate.py, measured against the existing labels on a dev split, and
are pinned in ops/classify_thresholds.json with the model version they were measured on.

Writes: public.mention_sentiment (model_version jev-1.13.0-absa-1 or glm-5.3-absa-1) and
public.mention_rejections. Both fire the triggers that mark the brand's page for refresh.

Egress: the text a judge reads leaves the database, so fetch_items counts its bytes in READ_BYTES and the
sweep's egress estimate adds them to the write-ahead log it measures.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from rubric import SYSTEM as RUBRIC, mark_target  # noqa: E402  the calibrated rubric, verbatim

JEV_MODEL = "jev-1.13.0"
MV_JEV = "jev-1.13.0-absa-1"
GLM_MODELS = {"glm-5.3-flash": "glm-5.3-flash-absa-1", "glm-5.3": "glm-5.3-absa-1"}
LABEL_CODE = {"neu": 0, "pos": 1, "neg": 2, "abstain": 3}
JEV_BATCH = 20
GLM_BATCH = 100
THRESHOLDS = os.path.join(ROOT, "ops", "classify_thresholds.json")
GLM_DEFAULT = "glm-5.3"
# Z.ai credits per 10,000 tokens at peak (uncached input, cached input, output); half that off-peak.
# The glm-assistant formula, checked against ~/.claude/scripts/zai_credits.py on 2026-10-02.
GLM_RATES = {"glm-5.3-flash": (2.3, 0.56, 8.0), "glm-5.3": (6.9, 1.7, 24.0)}
READ_BYTES = 0

# ---------------------------------------------------------------------------------------------- items
# The text a judge reads: the 1,200 characters around the matched name, cut IN THE DATABASE, so a
# 6,000-character post never leaves it whole.
ITEM_SQL = """
select m.brand_id, m.doc_id, m.created_utc, b.slug as brand_slug, b.name as brand_name,
       coalesce(c.name, '') as category, sr.name as subreddit, left(coalesce(t.link_title, ''), 160) as thread,
       m.matched_form,
       substr(txt.body, greatest(1, strpos(lower(txt.body), lower(m.matched_form)) - 600), 1200) as window,
       greatest(0, least(strpos(lower(txt.body), lower(m.matched_form)) - 1, 600)) as offset
  from unnest(%s::bigint[], %s::text[], %s::timestamptz[]) as k(brand_id, doc_id, created_utc)
  join public.mentions m on m.brand_id = k.brand_id and m.doc_id = k.doc_id and m.created_utc = k.created_utc
  -- one copy of a comment's text is kept, on one of its rows (migration 0019)
  cross join lateral (select coalesce(m.body, (select x.body from public.mentions x where x.doc_id = m.doc_id
                        and x.created_utc = m.created_utc and x.brand_id = m.body_from)) as body) txt
  join public.brands b on b.id = m.brand_id
  left join public.categories c on c.id = b.primary_category_id
  join public.subreddits sr on sr.id = m.subreddit_id
  left join public.threads t on t.id = m.thread_id
"""


def fetch_items(conn, keys: list[tuple]) -> list[dict]:
    if not keys:
        return []
    global READ_BYTES
    cur = conn.execute(ITEM_SQL, ([k[0] for k in keys], [k[1] for k in keys], [k[2] for k in keys]))
    cols = [d.name for d in cur.description]
    out = []
    for r in cur.fetchall():
        READ_BYTES += sum(len(str(v).encode()) for v in r if v is not None) + 16 * len(r)
        it = dict(zip(cols, r))
        it["text"] = mark_target(it["window"] or "", it["matched_form"] or "", int(it["offset"] or 0))
        out.append(it)
    return out


# ---------------------------------------------------------------------------------------------- Jev
GUIDE = ("You read Reddit text that mentions a software product. The span <<TARGET:...>> marks where the "
         "product was matched. Judge ONLY that product, as the author of the text sees it. These rules are "
         "the ones the index was labelled with until 2026:\n\n" + RUBRIC.split("Also return:")[0].strip())


def _typesafe():
    """The estate's metered Jev client: ~/.claude/api_helpers on the laptop, a copy in the image (RI_API_HELPERS)."""
    path = os.environ.get("RI_API_HELPERS") or os.path.expanduser("~/.claude/api_helpers")
    if path not in sys.path:
        sys.path.insert(0, path)
    import typesafe
    return typesafe


def jev_questions(j: int) -> dict:
    ts = _typesafe()
    return {
        f"e{j}": ts.noul(
            f"In items[{j}], does the marked span refer to the software product named in items[{j}].product, "
            "and not to another meaning of the same word, a different product, or the company in general?",
            true="yes: the marked span is this product", false="no: it means something else"),
        f"s{j}": ts.choice(
            f"In items[{j}], how does the AUTHOR feel about the product named in items[{j}].product? "
            "Follow the rules in `guide`.",
            {"pos": "positive about this product",
             "neg": "negative about this product (a price complaint counts; 'it's fine, I guess' counts)",
             "neu": "no opinion about this product: a factual mention, a question, a list, a complaint about "
                    "the whole category, or text the author quoted from someone else",
             "unsure": "cannot tell, including possible sarcasm"}),
    }


def jev_judge(items: list[dict], workers: int = 8, log=print) -> list[dict | None]:
    """-> per item {"e": P(this product), "probs": {pos,neg,neu,unsure}} or None (not checked)."""
    ts = _typesafe()
    client = ts.TypeSafeAPI(model=JEV_MODEL, caller="reddit-index-classify")
    reqs, spans = [], []
    for start in range(0, len(items), JEV_BATCH):
        chunk = items[start:start + JEV_BATCH]
        state = {"guide": GUIDE, "items": [
            {"subreddit": f"r/{it['subreddit']}", "thread": it["thread"],
             "product": f"{it['brand_name']} ({it['category']})" if it["category"] else it["brand_name"],
             "text": it["text"]} for it in chunk]}
        q = {}
        for j in range(len(chunk)):
            q.update(jev_questions(j))
        reqs.append((state, q))
        spans.append((start, len(chunk)))
    res = client.evaluate_many(reqs, workers=workers, model=JEV_MODEL)
    out: list[dict | None] = [None] * len(items)
    usd = 0.0
    errors: dict[str, int] = {}
    for (start, n), r in zip(spans, res):
        if not r or "_error" in r or (r.get("_meta") or {}).get("incomplete"):
            # a failure is residue, never a verdict; but it is COUNTED on the receipt (6 Oct: TypeSafe ran out of
            # credits, every Jev request answered 402, and the receipt said only "Jev decided 0")
            why = str((r or {}).get("_error") or ("incomplete" if r else "no answer"))[:120]
            errors[why] = errors.get(why, 0) + 1
            continue
        usd += float((r.get("_meta") or {}).get("usd") or 0)
        a = r.get("answers") or {}
        for j in range(n):
            e, s = a.get(f"e{j}"), a.get(f"s{j}")
            if not (isinstance(e, dict) and isinstance(s, dict) and "noul" in e and "probabilities" in s):
                continue
            out[start + j] = {"e": float(e["noul"]), "probs": {k: float(v) for k, v in s["probabilities"].items()}}
    jev_judge.last_usd = usd
    jev_judge.last_errors = errors
    return out


jev_judge.last_usd = 0.0
jev_judge.last_errors = {}


def decide(j: dict | None, t: dict) -> tuple[str, float] | None:
    """The precedence, as arithmetic. -> ("reject", conf) | (label, conf) | None (to GLM)."""
    if j is None:
        return None
    if j["e"] <= t["reject_below"]:
        return ("reject", 1 - j["e"])
    if j["e"] < t["product_at"]:
        return None
    probs = j["probs"]
    label = max(probs, key=probs.get)
    p = probs[label]
    if label == "unsure":
        return None
    if p >= t["label_at"][label]:
        return (label, p)
    return None


# ---------------------------------------------------------------------------------------------- GLM
# The judging rules are the calibrated rubric's, word for word. Only the OUTPUT is cut to the three fields
# the index stores: output tokens are GLM's bill (measured 2026-10-02: 143 output tokens a mention with the
# full field list, two thirds of the credits), and intensity, flags and evidence were never shown anywhere.
GLM_RULES = RUBRIC.split("Also return:")[0].rstrip()
GLM_OUTPUT = ("Also return:\n"
              "  confidence  0.0 to 1.0, how sure you are of the label\n"
              "  entity_ok   false if the marked span is NOT this software product at all —\n"
              "              the weekday, the herb, the verb, a different company's product\n\n"
              "Output ONLY a JSON object mapping each item id to a three-element array\n"
              "[label, confidence, entity_ok], for example {\"i1\": [\"neu\", 0.8, true], \"i2\": [\"pos\", 0.95, true]}.\n"
              "No prose, no markdown fence.")


def glm_prompt(items: list[dict]) -> str:
    """Items are numbered i1..iN in the prompt: a short id is ten output tokens cheaper per mention than
    doc id plus brand slug, and output tokens are GLM's bill."""
    blocks = []
    for n, it in enumerate(items, 1):
        blocks.append(f"### i{n}\nsubreddit: r/{it['subreddit']}\n"
                      f"thread: {it['thread']}\nproduct: {it['brand_name']}\ncomment:\n{it['text']}")
    return (GLM_RULES + "\n\n" + GLM_OUTPUT + "\n\nLabel each item below. Every id present, no id skipped. "
            "Return ONLY the JSON object. Do not search the web and do not run any command.\n\n"
            + "\n\n".join(blocks))


def _glm_answer(r) -> tuple | None:
    """[label, confidence, entity_ok] (or the object form) -> ("reject", conf) | (label, conf) | None."""
    if isinstance(r, list) and len(r) >= 3:
        r = {"label": r[0], "confidence": r[1], "entity_ok": r[2]}
    if not isinstance(r, dict):
        return None
    try:
        conf = float(r.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if r.get("entity_ok") is False or str(r.get("entity_ok")).lower() == "false":
        return ("reject", conf)
    lab = str(r.get("label") or "").lower()
    if lab not in LABEL_CODE:      # no label, or one the rubric does not have: not answered, stays queued
        return None
    return (lab, conf)


def _glm_env() -> dict:
    key = os.environ.get("ZAI_API_KEY")
    if not key:
        with open(os.path.expanduser("~/.claude/.zai.json")) as f:
            key = json.load(f)["api_key"]
    return {**os.environ, "CODEX_HOME": os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex-zai")),
            "ZAI_API_KEY": key}


RATE_LIMIT = re.compile(r"rate.?limit|too many requests|\b429\b|concurren", re.I)
# The plan's weekly or monthly allowance is used up (2026-10-07: "Weekly/Monthly Limit Exhausted. Your limit will
# reset at 2026-10-10 21:12:22"). Not a rate limit: no retry helps until the stated time, so the stage stops asking
# GLM, lets Jev settle what it can across the whole queue, and leaves the rest queued with its tries.
GLM_WALL = re.compile(r"(?:weekly|monthly)[^.]*limit[^.]*exhausted.*?reset at (\d{4}-\d\d-\d\d[ T]\d\d:\d\d(?::\d\d)?)", re.I | re.S)


def glm_wall_until(text: str) -> str | None:
    """The reset time a GLM wall error states, as UTC ISO. Z.ai does not say its zone; read as UTC+8 (Beijing), the
    earliest it can mean, so a wrong guess costs one refused GLM job after which the wall is read again."""
    m = GLM_WALL.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace("T", " ")
    t = dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S" if raw.count(":") == 2 else "%Y-%m-%d %H:%M")
    return t.replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _walled(rec: dict) -> bool:
    """A wall is in force until its reset time; a run that outlasts it asks GLM again."""
    w = rec.get("glm_walled_until")
    return bool(w) and dt.datetime.fromisoformat(w) > dt.datetime.now(dt.timezone.utc)


def glm_job(items: list[dict], model: str = "glm-5.3-flash", timeout: float = 900) -> tuple[dict | None, dict]:
    """One Codex CLI job on GLM. -> (answers keyed by item id, usage). A failed job carries usage["_error"]: what
    the provider or the CLI said, so a night's receipt can tell a rate limit from a fault (2026-10-05: Z.ai's
    request-rate limit, hit by two sessions sharing one plan, read only as "every job failed")."""
    with tempfile.TemporaryDirectory() as tmp:
        # The prompt goes in on stdin ("-"), never as an argument: Linux caps one argument at 128 KB, and a batch of
        # 100 long comments passed that on the first scheduled run (2026-10-04, "Argument list too long"). macOS
        # allows 1 MB, which is why the laptop never saw it.
        cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "--ephemeral", "--json",
               "-m", model, "-c", "model_reasoning_effort=low", "-"]
        try:
            p = subprocess.run(cmd, cwd=tmp, env=_glm_env(), input=glm_prompt(items), capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:   # one job that cannot run costs its items, not the stage
            return None, {"_error": f"timed out after {int(timeout)} s"}
        except OSError as e:
            return None, {"_error": f"could not start codex: {str(e)[:120]}"}
    text, usage, errors = None, {}, []
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t, it = e.get("type"), (e.get("item") or {})
        if t == "item.completed" and it.get("type") in ("agent_message", "assistant_message"):
            text = it.get("text")
        elif t == "item.completed" and it.get("type") == "error" and "Skill descriptions" not in str(it.get("message")):
            errors.append(str(it.get("message")))
        elif t in ("error", "turn.failed"):
            errors.append(str(e.get("message") or (e.get("error") or {}).get("message") or e)[:300])
        if t == "turn.completed":
            usage = e.get("usage") or {}
    if not text:
        tail = [x for x in p.stderr.splitlines() if x.strip() and "failed to load skill" not in x][-2:]
        usage = dict(usage, _error=(errors[-1] if errors else " | ".join(tail) or f"no answer (exit {p.returncode})")[:300])
        return None, usage
    m = re.search(r"\{.*\}", text, re.S)
    try:
        ans = json.loads(m.group(0)) if m else None
    except ValueError:
        ans = None
    if ans is None:
        usage = dict(usage, _error="the answer was not the JSON object asked for")
    return ans, usage


def glm_judge(items: list[dict], in_flight: int = 6, model: str = "glm-5.3-flash", log=print,
              deadline: float | None = None) -> tuple[list[tuple | None], dict]:
    """-> per item ("reject", conf) | (label, conf) | None, and the summed usage. spend["asked"] marks the items
    whose job came back (GLM saw them and answered or skipped them); an item whose job failed or never started was
    not asked, and must not lose one of its tries for it (review, 2026-10-04).

    Jobs the provider refused for its request-rate limit are tried again, up to three more rounds, after 1, 2 and
    4 minutes and at half the width each round (the plan is shared with other sessions; 2026-10-05). What still
    fails is counted by its error, and spend["rate_limited"] says whether every remaining failure was the limit."""
    out: list[tuple | None] = [None] * len(items)
    asked = [False] * len(items)
    spend = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "jobs": 0, "failed_jobs": 0,
             "skipped_jobs": 0, "retried_jobs": 0, "errors": {}}
    chunks = [(s, items[s:s + GLM_BATCH]) for s in range(0, len(items), GLM_BATCH)]
    spend["jobs"] = len(chunks)

    def one(c):
        # a job never runs past the stage's deadline: its timeout is what is left (at most 15 minutes)
        left = 900.0 if deadline is None else min(900.0, deadline - time.time())
        if left < 60:
            return "skipped", {}
        return glm_job(c[1], model, timeout=left)

    pending, width, last_err = chunks, max(1, in_flight), {}
    for rnd in range(4):
        if rnd:
            wait = 60 * 2 ** (rnd - 1)
            if deadline is not None and time.time() + wait + 120 > deadline:
                break
            log(f"    GLM: {len(pending)} jobs refused for the provider's rate limit; again in {wait} s at width {width}")
            time.sleep(wait)
            spend["retried_jobs"] += len(pending)
        again = []
        with ThreadPoolExecutor(width) as ex:
            for (start, chunk), (ans, usage) in zip(pending, ex.map(one, pending)):
                for k in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    spend[k] += int(usage.get(k) or 0)
                if ans == "skipped":
                    spend["skipped_jobs"] += 1
                    last_err.pop(start, None)
                    continue
                if not isinstance(ans, dict):
                    last_err[start] = usage.get("_error") or "no answer"
                    again.append((start, chunk))
                    continue
                last_err.pop(start, None)
                for j in range(len(chunk)):
                    asked[start + j] = True
                    v = _glm_answer(ans.get(f"i{j + 1}"))
                    if v is not None:
                        out[start + j] = v
        walls = [glm_wall_until(last_err.get(c[0], "")) for c in again]
        if any(walls):                                 # the allowance is used up: retrying cannot help
            spend["walled_until"] = max(w for w in walls if w)
            pending = again
            break
        limited = [c for c in again if RATE_LIMIT.search(last_err.get(c[0], ""))]
        if not limited or len(limited) < len(again):   # retry only a batch the limit alone refused
            pending = again
            break
        pending, width = again, max(1, width // 2)
    spend["failed_jobs"] = len(last_err)
    for e in last_err.values():
        key = e[:100]
        spend["errors"][key] = spend["errors"].get(key, 0) + 1
    spend["rate_limited"] = (bool(last_err) and all(RATE_LIMIT.search(e) for e in last_err.values())
                             and not spend.get("walled_until"))
    spend["asked"] = asked
    a, c, o = GLM_RATES[model]
    unc = spend["input_tokens"] - spend["cached_input_tokens"]
    peak = 1.0 if glm_peak_now() else 0.5
    spend["credits"] = round((unc * a + spend["cached_input_tokens"] * c + spend["output_tokens"] * o) / 10000 * peak, 1)
    return out, spend


def glm_peak_now() -> bool:
    """Z.ai bills double 03:00-07:00 Chile time (06:00-10:00 UTC while Chile is on UTC-3)."""
    h = time.gmtime().tm_hour
    return 6 <= h < 10


# ---------------------------------------------------------------------------------------------- write
def write(conn, items: list[dict], verdicts: list[tuple | None], mv: list[str],
          tried: list[bool] | None = None) -> dict:
    lab_rows, rej_rows = [], []
    for it, v, model in zip(items, verdicts, mv):
        if v is None:
            continue
        kind, conf = v
        if kind == "reject":
            rej_rows.append((it["doc_id"], it["brand_id"], model, conf, "not this product"))
        else:
            lab_rows.append((it["doc_id"], it["brand_id"], model, LABEL_CODE[kind], conf))
    labelled = rejected = 0
    with conn.transaction():
        # one statement each, so rowcount is the rows actually written: a row that already existed (ON CONFLICT)
        # is not counted, and the receipt equals the table (review, 2026-10-04)
        if lab_rows:
            labelled = conn.execute(
                "insert into public.mention_sentiment (doc_id, brand_id, model_version, label, intensity, conf, stage, "
                "is_comparative, is_recommendation, is_category_gripe, evidence_span, scored_at) "
                "select d, b, m, l, 0, c, 3, false, false, false, null, now() "
                "from unnest(%s::text[], %s::bigint[], %s::text[], %s::smallint[], %s::real[]) as v(d, b, m, l, c) "
                "on conflict do nothing",
                ([r[0] for r in lab_rows], [r[1] for r in lab_rows], [r[2] for r in lab_rows],
                 [r[3] for r in lab_rows], [r[4] for r in lab_rows])).rowcount
        if rej_rows:
            rejected = conn.execute(
                "insert into public.mention_rejections (doc_id, brand_id, model_version, conf, reason) "
                "select d, b, m, c, r from unnest(%s::text[], %s::bigint[], %s::text[], %s::real[], %s::text[]) "
                "as v(d, b, m, c, r) on conflict do nothing",
                ([r[0] for r in rej_rows], [r[1] for r in rej_rows], [r[2] for r in rej_rows],
                 [r[3] for r in rej_rows], [r[4] for r in rej_rows])).rowcount
        done = [(it["brand_id"], it["doc_id"], it["created_utc"]) for it, v in zip(items, verdicts) if v is not None]
        if done:
            conn.execute("delete from public.classify_queue q using unnest(%s::bigint[], %s::text[], %s::timestamptz[]) "
                         "as k(b, d, c) where q.brand_id = k.b and q.doc_id = k.d and q.created_utc = k.c",
                         ([x[0] for x in done], [x[1] for x in done], [x[2] for x in done]))
        # Only what no judge answered is marked as tried (five tries, then it waits for a person). Marking every
        # row before judging it rewrote 2,000 queue rows a batch only to delete them a second later: write-ahead
        # log the egress counter bills (measured 2026-10-02).
        tried = tried if tried is not None else [True] * len(items)
        left = [(it["brand_id"], it["doc_id"], it["created_utc"])
                for it, v, t in zip(items, verdicts, tried) if v is None and t]
        if left:
            conn.execute("update public.classify_queue q set attempts = attempts + 1 "
                         "from unnest(%s::bigint[], %s::text[], %s::timestamptz[]) as k(b, d, c) "
                         "where q.brand_id = k.b and q.doc_id = k.d and q.created_utc = k.c",
                         ([x[0] for x in left], [x[1] for x in left], [x[2] for x in left]))
    return {"labelled": labelled, "rejected": rejected}


# ---------------------------------------------------------------------------------------------- the stage
def run(conn, cfg: dict, deadline: float, should_stop=lambda: None, log=print) -> dict:
    with open(THRESHOLDS, encoding="utf-8") as f:
        t = json.load(f)
    if t.get("model") != JEV_MODEL:
        raise RuntimeError(f"thresholds were measured on {t.get('model')}, not {JEV_MODEL}: recalibrate")
    model = cfg.get("glm_model", GLM_DEFAULT)
    rec = {"queued": 0, "jev_decided": 0, "glm_decided": 0, "labelled": 0, "rejected": 0, "not_checked": 0,
           "jev_usd": 0.0, "glm_credits": 0.0, "glm_model": model, "read_bytes": 0, "stopped": None,
           # allowance_used: the planned nightly allowance (credits, dollars, time) ran out with mentions still
           # queued. A normal end while there is a backlog; on the receipt, never an alert. stopped: a real limit.
           "allowance_used": None}
    read0 = READ_BYTES
    last_batch = {"glm": 0.0, "jev": 0.0}
    rec["queued"] = conn.execute("select count(*) from public.classify_queue").fetchone()[0]
    wall = known_glm_wall(conn)
    if wall:
        rec["glm_walled_until"] = wall
        log(f"    classify: GLM's allowance is used up until {wall} (a recent run's receipt); Jev only until then")
    limit = int(cfg.get("max_items", 60000))
    try:
        _loop(conn, cfg, t, model, rec, last_batch, limit, deadline, should_stop, log)
    except Exception as e:  # noqa: BLE001 - what was judged and written before the error stays on the receipt
        rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        log(f"    classify: stopped by an error after {rec['labelled'] + rec['rejected']} written: {rec['error']}")
    rec["jev_usd"] = round(rec["jev_usd"], 4)
    rec["glm_credits"] = round(rec["glm_credits"], 1)
    rec["read_bytes"] = READ_BYTES - read0
    rec["left_in_queue"] = conn.execute("select count(*) from public.classify_queue").fetchone()[0]
    return rec


def known_glm_wall(conn) -> str | None:
    """A GLM wall a run in the last 8 days recorded, if its reset time is still ahead."""
    try:
        row = conn.execute(
            "select max(notes->'stages'->'classify'->>'glm_walled_until') from public.pipeline_runs "
            "where stage = 'sweep' and started_at > now() - interval '8 days' "
            "and notes->'stages'->'classify' ? 'glm_walled_until'").fetchone()
    except Exception:  # noqa: BLE001 - no reading means GLM is tried; a refused job reads the wall again
        return None
    w = row[0] if row else None
    if w and dt.datetime.fromisoformat(w) > dt.datetime.now(dt.timezone.utc):
        return w
    return None


def _loop(conn, cfg, t, model, rec, last_batch, limit, deadline, should_stop, log) -> None:
    taken = 0
    cursor = None   # with GLM off, Jev's residue stays queued: page past it instead of selecting it again
    while taken < limit:
        glm_on = cfg.get("glm", True) and not _walled(rec)
        if time.time() > deadline:
            rec["allowance_used"] = "the time set aside for classification ended"
            break
        reason = should_stop()
        if reason:
            rec["stopped"] = reason
            break
        if glm_on and glm_peak_now():
            rec["allowance_used"] = "Z.ai peak hours (06:00-10:00 UTC): ended rather than leave GLM's share unjudged"
            break
        # the caps are checked BEFORE a batch is spent, on what the last batch cost
        if rec["glm_credits"] + last_batch["glm"] > float(cfg.get("glm_credits_max", 3000)):
            rec["allowance_used"] = f"tonight's GLM allowance ({cfg.get('glm_credits_max')} credits) is used"
            break
        if rec["jev_usd"] + last_batch["jev"] > float(cfg.get("jev_usd_max", 1.0)):
            rec["allowance_used"] = f"tonight's Jev allowance (${cfg.get('jev_usd_max')}) is used"
            break
        # What arrived in the last day first (newest first), then the backlog in brand order. Brand order is the
        # egress fix of 2026-10-05: every label inserts into two large indexes and deletes from the queue's, and
        # after each checkpoint the first change to a page ships the whole 8 KB page to backup storage. Newest-first
        # scattered a batch across the indexes (8.7 KB of egress a mention, measured that morning); in brand order
        # the queue's and mention_sentiment_latest_idx's touches are adjacent.
        n = min(2000, limit - taken)
        if not glm_on:
            keys = conn.execute("select brand_id, doc_id, created_utc from public.classify_queue where attempts < 5 "
                                "and (brand_id, doc_id, created_utc) > (%s, %s, %s) "
                                "order by brand_id, doc_id, created_utc limit %s",
                                (*(cursor or (-1, "", dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc))), n)).fetchall()
            if keys:
                cursor = tuple(keys[-1])
        else:
            keys = conn.execute("select brand_id, doc_id, created_utc from public.classify_queue "
                                "where attempts < 5 and enqueued_at > now() - interval '26 hours' "
                                "order by enqueued_at desc, created_utc desc limit %s", (n,)).fetchall()
            if len(keys) < n:
                keys += conn.execute("select brand_id, doc_id, created_utc from public.classify_queue "
                                     "where attempts < 5 and enqueued_at <= now() - interval '26 hours' "
                                     "order by brand_id, doc_id, created_utc limit %s", (n - len(keys),)).fetchall()
        keys.sort(key=lambda k: (k[0], k[1]))   # the batch's writes in brand order too
        if not keys:
            break
        taken += len(keys)
        items = fetch_items(conn, keys)
        # A queued key whose mention row is gone (purged, or retention removed it) can never be judged; left in
        # the queue it was selected again every batch, forever (review, 2026-10-03).
        found = {(it["brand_id"], it["doc_id"], it["created_utc"]) for it in items}
        gone = [k for k in keys if (k[0], k[1], k[2]) not in found]
        if gone:
            rec["gone_from_queue"] = rec.get("gone_from_queue", 0) + conn.execute(
                "delete from public.classify_queue q using unnest(%s::bigint[], %s::text[], %s::timestamptz[]) "
                "as k(b, d, c) where q.brand_id = k.b and q.doc_id = k.d and q.created_utc = k.c",
                ([k[0] for k in gone], [k[1] for k in gone], [k[2] for k in gone])).rowcount
        if not items:
            continue
        j = jev_judge(items, log=log)
        rec["jev_usd"] += jev_judge.last_usd
        last_batch["jev"] = jev_judge.last_usd
        for why, k in jev_judge.last_errors.items():
            rec.setdefault("jev_errors", {})[why] = rec.get("jev_errors", {}).get(why, 0) + k
        verdicts = [decide(x, t) for x in j]
        models = [MV_JEV if v else None for v in verdicts]
        rec["jev_decided"] += sum(v is not None for v in verdicts)
        residue = [i for i, v in enumerate(verdicts) if v is None]
        # an item counts a try only when a judge was asked and could not settle it: Jev's residue with GLM switched
        # off was never asked (the smoke test of 5 Oct took a try from 106 items that way)
        tried = [True] * len(items) if glm_on else [v is not None for v in verdicts]
        glm_down = glm_limited = False
        if residue and glm_on:
            g, spend = glm_judge([items[i] for i in residue], in_flight=int(cfg.get("glm_in_flight", 6)),
                                 model=model, log=log, deadline=deadline)
            rec["glm_credits"] += spend["credits"]
            last_batch["glm"] = spend["credits"]
            rec["glm_failed_jobs"] = rec.get("glm_failed_jobs", 0) + spend["failed_jobs"]
            rec["glm_retried_jobs"] = rec.get("glm_retried_jobs", 0) + spend["retried_jobs"]
            for k, n in spend["errors"].items():   # what the provider said, on the receipt
                rec.setdefault("glm_errors", {})[k] = rec.get("glm_errors", {}).get(k, 0) + n
            for i, v, a in zip(residue, g, spend["asked"]):
                tried[i] = a          # an item whose GLM job failed or never ran keeps its tries
                if v is not None:
                    verdicts[i], models[i] = v, GLM_MODELS[model]
                    rec["glm_decided"] += 1
            # every job of the batch failed: GLM (or the codex CLI) is down, not the items. Stop asking tonight.
            started = spend["jobs"] - spend["skipped_jobs"]   # jobs the deadline left unstarted are not failures
            glm_down = started > 0 and spend["failed_jobs"] == started
            glm_limited = glm_down and spend["rate_limited"]
            if spend.get("walled_until"):   # the allowance is used up: Jev only from the next batch, no stop
                rec["glm_walled_until"] = spend["walled_until"]
                rec["allowance_used"] = (f"GLM's plan allowance is used up until {spend['walled_until']}: Jev settled "
                                         f"what it could across the queue, the rest stays queued with its tries")
                log(f"    classify: GLM refused: its allowance is used up until {spend['walled_until']}; Jev only from here")
                glm_down = glm_limited = False
        w = write(conn, items, verdicts, [m or MV_JEV for m in models], tried)
        rec["labelled"] += w["labelled"]
        rec["rejected"] += w["rejected"]
        rec["not_checked"] += sum(v is None for v in verdicts)
        log(f"    classify: {taken} taken, {rec['labelled']} labelled, {rec['rejected']} not this product, "
            f"{rec['not_checked']} not checked; Jev ${rec['jev_usd']:.3f}, GLM {rec['glm_credits']:.0f} credits", flush=True)
        if glm_limited:   # the shared plan's request-rate limit held after the retries: a planned limit, not a fault
            rec["allowance_used"] = (f"Z.ai's request-rate limit (the GLM plan is shared with other sessions) refused "
                                     f"a whole batch after {spend['retried_jobs']} retries; what Jev settled was "
                                     f"written, the rest keeps its tries")
            break
        if glm_down:
            rec["error"] = (f"every GLM job of a batch failed ({spend['failed_jobs']} of {spend['jobs']}): "
                            f"{next(iter(spend['errors']), 'no error text')}; what Jev settled was written, the rest "
                            f"keeps its tries")
            break
        if rec["jev_usd"] > float(cfg.get("jev_usd_max", 1.0)):
            rec["allowance_used"] = f"tonight's Jev allowance (${cfg.get('jev_usd_max')}) is used"
            break
        if rec["glm_credits"] > float(cfg.get("glm_credits_max", 3000)):
            rec["allowance_used"] = f"tonight's GLM allowance ({cfg.get('glm_credits_max')} credits) is used"
            break
