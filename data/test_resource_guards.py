#!/usr/bin/env python3
"""The preflight resource gate must refuse a box that cannot carry a wave — and must NOT
refuse one that can.

INCIDENT (2026-08-23, second occurrence of the same shape; ~40 min lost plus the retry
budget it fed). The gate refused to start for 20 minutes on a perfectly healthy machine:

    free 2,623 MB   against a 2,220 MB need for a 6-wide wave
    swap  20,478 MB against a 26,000 MB hard limit
    swap  SHRINKING by 40 MB over the sample
    swap  95%       <- the only number the gate looked at

macOS sizes the swap file to demand, so a busy-but-healthy box reads 90-95% indefinitely.
A percentage is meaningless without the absolute number behind it. The same file had already
been recalibrated once for this exact false positive two days earlier (2026-08-22), and
`docs/post-mortem-2026-08-24.md` Class E records it with "No regression test." This is it.

The fix makes every %-based refusal conditional on the absolute free-memory figure and on
swap actually GROWING. What it protects, file:line:

  ~/.claude/scripts/fleet_preflight.py:113  the % backstop, now `swap_pct >= SWAP_CEILING
                                            AND used >= SWAP_HARD_MB * 0.9`
  ~/.claude/scripts/fleet_preflight.py:125  growth is consulted only past SWAP_WATCH_MB
  data/pipeline_supervisor.py:16            "never a % of the macOS swap pool"
  data/pipeline_supervisor.py:223           gate() — the supervisor's half
  data/pipeline_supervisor.py:47,402        a refusal is its own outcome ('busy') and spends
                                            NEITHER retry budget. Charged to a budget, a
                                            false refusal burned 3 attempts in 5 minutes.
  data/run_discovery_safe.py:10,57          the same gate, reached by the same import

fleet_preflight.py lives OUTSIDE the repo tree (five repo modules reach it via
`sys.path.insert(0, '~/.claude/scripts')`). This fixture resolves it without hardcoding any
absolute path: $FLEET_PREFLIGHT_PY, then <repo>/scripts, <repo>/vendor, <repo>/data, then
~/.claude/scripts. Drop a copy at <repo>/scripts/fleet_preflight.py and it wins — that is how
a throwaway tree copy gets tested instead of the live guard.

A SECOND family of refusals lives in the same function and was invisible to every scenario
below until an audit on 2026-08-24: the ones that need the FLEET to answer. `status()` asks
/health for the concurrency cap and the running-job count, and this fixture stubbed `_req`
to raise — so `cap` came back None, `running` came back 0, and both branches were dead code
under test. Deleting either one left all 30 checks green:

  ~/.claude/scripts/fleet_preflight.py:135  want > cap — the wave-wider-than-the-box refusal.
                                            The 2026-08-21 OOM was 60 slots on a box that
                                            holds 12; fleet.env fixes the cap and THIS is
                                            what makes a caller respect it.
  ~/.claude/scripts/fleet_preflight.py:145  codex processes the fleet cannot account for —
                                            a dead submitter's orphans, which is the third
                                            of the three compounding causes of that OOM.

Both are now driven with a scripted /health, and a structural check derived from the guard's
own source refuses to let a NEW refusal branch be added without a scenario reaching it: every
`raise SystemExit` inside preflight() must be the line some scenario below actually raised
from, recorded off the live traceback rather than a list typed in here.

The gate reads the machine inline through `subprocess.run` (sysctl vm.swapusage, vm_stat,
pgrep) and `os.getloadavg`. Nothing is extracted or refactored to test it: those two seams
are stubbed on the loaded module, and any unscripted spawn raises. `swap_growth_mb()` sleeps
15 s by design, so it is replaced by the scenario's scripted delta — the growth VALUE is the
machine reading under test, and the decision made from it stays real code.

  python3 data/test_resource_guards.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import types
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


# --------------------------------------------------------------------------- the guard itself

PREFLIGHT_CANDIDATES = [
    os.environ.get("FLEET_PREFLIGHT_PY") or "",
    os.path.join(ROOT, "scripts", "fleet_preflight.py"),
    os.path.join(ROOT, "vendor", "fleet_preflight.py"),
    os.path.join(HERE, "fleet_preflight.py"),
    os.path.expanduser("~/.claude/scripts/fleet_preflight.py"),
]

# The FLEET_* env vars override every threshold at import time. A shell that happens to carry
# one would silently re-tune the gate under the fixture, so they are cleared for the load.
TUNABLES = ("FLEET_SWAP_CEILING", "FLEET_LOAD_CEILING", "FLEET_MB_PER_JOB",
            "FLEET_FREE_MARGIN_MB", "FLEET_SWAP_GROWTH_MB", "FLEET_SWAP_WATCH_MB",
            "FLEET_SWAP_HARD_MB")


def preflight_path():
    for p in PREFLIGHT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


PFPATH = preflight_path()


def load_preflight():
    """A fresh copy of the gate per scenario, so one scenario's stubs cannot leak into the next."""
    saved = {k: os.environ.pop(k) for k in TUNABLES if k in os.environ}
    try:
        spec = importlib.util.spec_from_file_location("fp_under_test", PFPATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        os.environ.update(saved)


class Spawned(Exception):
    """An unscripted subprocess: the fixture would have read the real machine."""


class _Subproc:
    """Stands in for the gate's `subprocess`. Only the three readings it is allowed to take
    are scripted; anything else is a real spawn and must blow up loudly."""

    def __init__(self, swap_text, vm_text, codex_pids=0):
        self.swap_text, self.vm_text, self.calls = swap_text, vm_text, []
        # `pgrep -f 'codex exec'` — how many codex processes the box is carrying. 0 keeps the
        # historical behaviour of every scenario written before the fleet was scriptable.
        self.pgrep_text = "\n".join(str(9000 + i) for i in range(codex_pids))

    def run(self, cmd, **kw):
        self.calls.append(list(cmd))
        if list(cmd[:2]) == ["sysctl", "vm.swapusage"]:
            return SimpleNamespace(stdout=self.swap_text, stderr="", returncode=0)
        if list(cmd[:1]) == ["vm_stat"]:
            return SimpleNamespace(stdout=self.vm_text, stderr="", returncode=0)
        if list(cmd[:1]) == ["pgrep"]:
            return SimpleNamespace(stdout=self.pgrep_text, stderr="",
                                   returncode=0 if self.pgrep_text else 1)
        raise Spawned(f"unstubbed spawn: {cmd}")


class _OsShim:
    """Only getloadavg is faked; everything else is the real os module."""

    def __init__(self, load1):
        self._load1 = load1

    def getloadavg(self):
        return (self._load1, self._load1, self._load1)

    def __getattr__(self, name):
        return getattr(os, name)


def _offline_req(path, method="GET"):
    raise RuntimeError("fleet stubbed offline")


def _fleet_req(health):
    """The gate's HTTP seam. `None` = the fleet is unreachable, which is what every scenario
    written before 2026-08-24 assumed and is why the two fleet-dependent refusals below were
    unreachable. A dict is served as /health; nothing else is ever answered, so a scenario
    that reaches for another endpoint fails loudly instead of silently going online."""
    if health is None:
        return _offline_req

    def req(path, method="GET"):
        if path == "/health":
            return dict(health)
        raise RuntimeError(f"fleet stubbed offline: {path}")
    return req


def sysctl_swapusage(total_mb, used_mb):
    return (f"vm.swapusage:  total = {total_mb:.2f}M  used = {used_mb:.2f}M  "
            f"free = {total_mb - used_mb:.2f}M  (encrypted)")


def vm_stat_text(free_mb):
    """Real vm_stat shape. free_mb lands entirely in 'Pages free' — the gate sums
    free + inactive + purgeable at 16 KB a page."""
    pages = int(free_mb * 1024 * 1024 / 16384)
    return "\n".join([
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)",
        f"Pages free:                               {pages}.",
        "Pages active:                             131072.",
        "Pages inactive:                           0.",
        "Pages speculative:                        0.",
        "Pages throttled:                          0.",
        "Pages wired down:                         131072.",
        "Pages purgeable:                          0.",
    ])


ALL_SPAWNS = []
REFUSED_AT = set()      # source lines of the guard that some scenario actually raised from


def decide(swap_total_mb, swap_used_mb, free_mb, growth_mb, load1=2.0, want=6,
           fleet=None, codex_pids=0):
    """Run the REAL preflight against one synthetic machine reading.

    `fleet` is the /health body (None = unreachable), `codex_pids` the number of codex
    processes on the box. Returns ('allow', status_dict) or ('refuse', message)."""
    m = load_preflight()
    sp = _Subproc(sysctl_swapusage(swap_total_mb, swap_used_mb), vm_stat_text(free_mb),
                  codex_pids=codex_pids)
    m.subprocess = sp
    m.os = _OsShim(load1)
    m._req = _fleet_req(fleet)                 # no sockets, no config file
    m.swap_growth_mb = lambda seconds=15: float(growth_mb)   # the real one sleeps 15 s
    try:
        try:
            s = m.preflight(want=want, quiet=True)
            return ("allow", s)
        except SystemExit as e:
            # which `raise SystemExit` fired, read off the live traceback. Derived, never
            # typed: check 8d below turns a NEW unexercised refusal branch red.
            tb = sys.exc_info()[2]
            while tb.tb_next:
                tb = tb.tb_next
            REFUSED_AT.add(tb.tb_lineno)
            return ("refuse", str(e))
    finally:
        ALL_SPAWNS.extend(sp.calls)


print("Preflight resource gate\n")

check("the gate is resolvable without hardcoding a repo path", PFPATH is not None,
      f"tried {[p for p in PREFLIGHT_CANDIDATES if p]}")

if PFPATH is None:
    print("\n1 FAILURES")
    sys.exit(1)

print(f"  (gate under test: {PFPATH})\n")

_m = load_preflight()
check("the incident's arithmetic still holds: a 6-wide wave needs 2,220 MB",
      _m.MB_PER_JOB * 6 + _m.FREE_MARGIN_MB == 2220,
      f"{_m.MB_PER_JOB}/job + {_m.FREE_MARGIN_MB} margin")

# 1. THE REGRESSION, replayed with the incident's own numbers.
#    95% swap, 2,623 MB free against a 2,220 MB need, swap shrinking 40 MB. Nothing is wrong
#    with this box and the gate refused it for 20 minutes.
verdict, msg = decide(swap_total_mb=21504, swap_used_mb=20478, free_mb=2623, growth_mb=-40)
check("95% swap + 2,623 MB free + swap SHRINKING is ALLOWED (the false refusal)",
      verdict == "allow", f"refused: {msg}")

# 2. 95% swap on its own is NOT the backstop: 20,478 MB is below 90% of the hard limit, so
#    what refuses this box is free RAM, and the message must say so. Revert the fix to a bare
#    `if swap_pct >= SWAP_CEILING` and this pair goes red on the message alone.
verdict, msg = decide(swap_total_mb=21504, swap_used_mb=20478, free_mb=900, growth_mb=-40)
check("95% swap + only 900 MB free is REFUSED", verdict == "refuse", f"allowed: {msg}")
check("...and the refusal names the ABSOLUTE shortfall, not the percentage — 95% alone did "
      "not fire the backstop", verdict == "refuse" and "900 MB free" in msg, msg)

# 2b. THE BACKSTOP ITSELF, which nothing above ever reached (found 2026-08-24 by check 8d):
#     both conjuncts true at once — 96% AND 24,000 MB, which is past 90% of the 26,000 MB
#     hard limit but not yet at it. Free RAM is ample and swap is flat, so this refusal can
#     only be the backstop.
verdict, msg = decide(swap_total_mb=25000, swap_used_mb=24000, free_mb=8000, growth_mb=0)
check("96% swap AND 24,000 MB used (90% of the hard limit) is REFUSED by the backstop",
      verdict == "refuse", f"allowed: {msg}")
check("...naming both conjuncts, the percentage AND the absolute figure",
      verdict == "refuse" and "swap at 96% AND 24000 MB" in msg, msg)

# 2c. ...and the same absolute figure at a LOW percentage is ALLOWED. The backstop needs
#     BOTH; drop the percentage conjunct and this goes red.
verdict, msg = decide(swap_total_mb=60000, swap_used_mb=24000, free_mb=8000, growth_mb=0)
check("the same 24,000 MB of swap at 40% is ALLOWED — the backstop needs both conjuncts",
      verdict == "allow", f"refused: {msg}")

# 3. low swap % does not excuse a starved box: free RAM is the primary gate on its own
verdict, msg = decide(swap_total_mb=12000, swap_used_mb=3000, free_mb=900, growth_mb=0)
check("25% swap + only 900 MB free is REFUSED (free RAM gates on its own)",
      verdict == "refuse", f"allowed: {msg}")
check("...naming the shortfall", verdict == "refuse" and "900 MB free" in msg, msg)

# 4. healthy on every axis
verdict, msg = decide(swap_total_mb=12000, swap_used_mb=3000, free_mb=8000, growth_mb=10)
check("a box healthy on every axis is ALLOWED", verdict == "allow", f"refused: {msg}")

# 5. growth is only a signal past the watch line. A 600 MB swing at 12,000 MB used is macOS
#    moving pages; the 2026-08-23 tuning note records a 200 MB gate refusing a 3 GB-free box.
verdict, msg = decide(swap_total_mb=12600, swap_used_mb=12000, free_mb=3000, growth_mb=600)
check("swap swinging +600 MB BELOW the watch line is ALLOWED", verdict == "allow",
      f"refused: {msg}")

# 6. ...but high AND climbing is the OOM signature and must still refuse
verdict, msg = decide(swap_total_mb=23100, swap_used_mb=22000, free_mb=8000, growth_mb=900)
check("swap high (22,000 MB) AND climbing +900 MB is REFUSED", verdict == "refuse",
      f"allowed: {msg}")
check("...saying it is climbing", verdict == "refuse" and "climbing" in msg, msg)

# 7. the absolute hard limit refuses on its own, with plenty of free RAM and a low percentage
verdict, msg = decide(swap_total_mb=40000, swap_used_mb=26500, free_mb=8000, growth_mb=-100)
check("swap past the 26,000 MB hard limit is REFUSED even at 66% and 8 GB free",
      verdict == "refuse", f"allowed: {msg}")
check("...naming the hard limit", verdict == "refuse" and "hard limit" in msg, msg)

# 8. a saturated box still refuses (the axis that is not memory)
verdict, msg = decide(swap_total_mb=12000, swap_used_mb=3000, free_mb=8000, growth_mb=0,
                      load1=99.0)
check("load 99 is REFUSED", verdict == "refuse", f"allowed: {msg}")

# 8b. THE FLEET CAP — the refusal that stops a wave being launched wider than the box can
#     hold. The 2026-08-21 OOM was 60 slots on a machine that carries 12; fleet.env fixes
#     the cap at 12 and this branch is the only thing that makes a caller respect it.
#     Every scenario above stubs the fleet UNREACHABLE, so `cap` is None and the branch is
#     skipped — which is exactly why deleting it left all 30 checks green (audit 2026-08-24).
HEALTHY = dict(swap_total_mb=12000, swap_used_mb=3000, free_mb=12000, growth_mb=0)
FLEET_CAP_12 = {"running": 0, "queued": 0, "max_concurrency": 12}

verdict, msg = decide(**HEALTHY, want=13, fleet=FLEET_CAP_12)
check("a 13-wide wave against a fleet cap of 12 is REFUSED", verdict == "refuse",
      f"allowed: {msg}")
check("...naming the wave asked for and the cap it exceeded",
      verdict == "refuse" and "asked for 13 in flight" in msg and "fleet cap is 12" in msg,
      msg)

# the boundary, on the SAME box: only `want` changed, so nothing but the cap can explain it
verdict, msg = decide(**HEALTHY, want=12, fleet=FLEET_CAP_12)
check("the same box asked for exactly the cap (12) is ALLOWED — the line is >, not >=",
      verdict == "allow", f"refused: {msg}")
verdict, msg = decide(**HEALTHY, want=11, fleet=FLEET_CAP_12)
check("a wave under the cap is ALLOWED", verdict == "allow", f"refused: {msg}")

# and an unreachable fleet reports no cap at all, which must not become a cap of zero
verdict, msg = decide(**HEALTHY, want=64, fleet=None)
check("an UNREACHABLE fleet knows no cap and must not manufacture a refusal from it",
      verdict == "allow", f"refused: {msg}")

# 8c. UNACCOUNTED codex processes — the third of the three compounding causes of the
#     2026-08-21 OOM (killed Bash calls leaving server-side jobs alive). Also dead under
#     test until now: with the fleet unreachable `running` defaults to 0 AND pgrep was
#     stubbed to find nothing, so the subtraction was 0 - 0 in every scenario.
FLEET_IDLE = {"running": 0, "queued": 0, "max_concurrency": 64}

verdict, msg = decide(**HEALTHY, want=6, fleet=FLEET_IDLE, codex_pids=5)
check("5 codex processes the fleet does not claim is REFUSED", verdict == "refuse",
      f"allowed: {msg}")
check("...naming the count and calling it unaccounted for",
      verdict == "refuse" and "5 codex processes" in msg and "unaccounted for" in msg, msg)

verdict, msg = decide(**HEALTHY, want=6, fleet=FLEET_IDLE, codex_pids=4)
check("4 unaccounted processes is under the line and ALLOWED (the line is >4)",
      verdict == "allow", f"refused: {msg}")

# the deliberate hole in that branch: work the fleet DOES claim is ours, and a resumable
# driver has to be able to top up behind it. Blocking on the raw count made every resume
# impossible, which is how a guard ends up disabled.
verdict, msg = decide(**HEALTHY, want=6, fleet={"running": 4, "queued": 0,
                                                "max_concurrency": 64}, codex_pids=8)
check("8 codex processes the fleet CLAIMS (4 jobs x parent+child) is ALLOWED",
      verdict == "allow", f"refused: {msg}")

# 8d. STRUCTURAL, and the reason 8b/8c existed to be found: every refusal the guard declares
#     must be one a scenario above actually raised from. The branch set is read out of the
#     guard's own source and matched against traceback line numbers recorded live, so a NEW
#     `raise SystemExit` added to preflight() turns this red until a scenario reaches it. A
#     list of expected branches typed in here would go stale the same way the fixture did.
_src = open(PFPATH).read().splitlines()
_start = next((i for i, l in enumerate(_src) if l.startswith("def preflight(")), None)
_end = next((i for i in range(_start + 1, len(_src)) if _src[i].startswith("def ")),
            len(_src)) if _start is not None else 0
DECLARED_REFUSALS = {i + 1 for i in range(_start or 0, _end)
                     if _src[i].lstrip().startswith("raise SystemExit(")}
check("the branch scan found preflight's refusals (an empty set would pass the next check "
      "by saying nothing)", len(DECLARED_REFUSALS) >= 6, f"found {sorted(DECLARED_REFUSALS)}")
check("every refusal branch preflight declares was reached by a scenario above",
      DECLARED_REFUSALS <= REFUSED_AT,
      f"never raised from: lines {sorted(DECLARED_REFUSALS - REFUSED_AT)}")

# 9. nothing above read the real machine
bad = [c for c in ALL_SPAWNS
       if list(c[:2]) != ["sysctl", "vm.swapusage"] and list(c[:1]) not in (["vm_stat"], ["pgrep"])]
check("no scenario shelled out to anything unscripted", not bad, str(bad[:3]))
check("the gate really did read the stubbed sysctl/vm_stat",
      any(list(c[:2]) == ["sysctl", "vm.swapusage"] for c in ALL_SPAWNS)
      and any(list(c[:1]) == ["vm_stat"] for c in ALL_SPAWNS))


# --------------------------------------------------------------- the supervisor's half of it

def supervisor(tmp):
    """pipeline_supervisor bound to a throwaway state dir. Never touches the live run."""
    spec = importlib.util.spec_from_file_location(
        "sup_guard_" + os.path.basename(tmp), os.path.join(HERE, "pipeline_supervisor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PDIR = tmp
    m.LOG = os.path.join(tmp, "pipeline.log")
    m.STATE = os.path.join(tmp, "state.json")
    m.LEGACY = os.path.join(tmp, "nonexistent.log")
    # NEVER let a test touch the real launchd agent — uninstall() deletes a plist.
    m.AGENT_PLIST = os.path.join(tmp, "agent.plist")
    m.AGENT_LABEL = "com.vladshvets.test-does-not-exist"
    m.COOLDOWN_S = m.NET_COOLDOWN_S = m.BUSY_COOLDOWN_S = 0
    m.POLL_S = 0
    m.uninstalls = []
    m.uninstall = lambda: m.uninstalls.append(True)
    open(m.LOG, "a").close()
    return m


print()

# 10. gate() maps the guard's SystemExit onto a refusal, and does not invent one
with tempfile.TemporaryDirectory() as tmp:
    m = supervisor(tmp)
    prior = sys.modules.get("fleet_preflight")
    fake = types.ModuleType("fleet_preflight")

    def refusing(want=8, quiet=False):
        raise SystemExit("REFUSING: 900 MB free, a 6-wide wave needs 2220 MB "
                         "(120 MB/job + 1500 MB margin).")
    fake.preflight = refusing
    sys.modules["fleet_preflight"] = fake
    try:
        check("gate() refuses when the guard refuses", m.gate(6) is False)
        fake.preflight = lambda want=8, quiet=False: {"free_mb": 8000}
        check("gate() allows when the guard allows", m.gate(6) is True)
    finally:
        if prior is not None:
            sys.modules["fleet_preflight"] = prior
        else:
            sys.modules.pop("fleet_preflight", None)

# 11. a refusal is its own return code, distinct from a crash
with tempfile.TemporaryDirectory() as tmp:
    m = supervisor(tmp)
    check("a refusal has its own reserved return code", m.PREFLIGHT_REFUSED_RC == 90,
          str(m.PREFLIGHT_REFUSED_RC))
    m.gate = lambda w: False
    started = []
    m.run = lambda args, label: started.append(label) or 0
    check("attempt() returns the refusal code, not a crash code",
          m.attempt() == m.PREFLIGHT_REFUSED_RC)
    check("a refused attempt starts no lane at all", started == [], str(started))

# 12. THE SECOND-ORDER COST: a refusal must spend NEITHER retry budget.
#     Charged to one, six false refusals end the run for good — which is what a %-gate on a
#     healthy box was doing on 2026-08-23 (3 budget in 5 minutes).
with tempfile.TemporaryDirectory() as tmp:
    m = supervisor(tmp)
    m.lane_pids = lambda: []
    started = []
    m.run = lambda args, label: started.append(label) or 0

    def refusing_gate(width):
        # exactly what the real gate does: log the guard's own REFUSING line, return False
        m.say("preflight refused: REFUSING: 2623 MB free, a 6-wide wave needs 2220 MB "
              "(120 MB/job + 1500 MB margin).")
        return False
    m.gate = refusing_gate

    slept = []

    def counted(secs):
        slept.append(secs)
        if len(slept) >= 6:          # the loop is otherwise unbounded by design
            raise SystemExit("bounded by the fixture")
    m.time = SimpleNamespace(sleep=counted, time=time.time, strftime=time.strftime)
    sys.argv = ["x"]
    try:
        m.main()
    except SystemExit:
        pass
    st = json.load(open(m.STATE))
    check("a preflight refusal spends NO genuine budget", st.get("attempts", 0) == 0,
          f"attempts={st.get('attempts')}")
    check("a preflight refusal spends NO network budget", st.get("net_attempts", 0) == 0,
          f"net_attempts={st.get('net_attempts')}")
    check("a preflight refusal is counted as a busy wait instead",
          st.get("busy_waits", 0) >= 1, f"busy_waits={st.get('busy_waits')}")
    check("a refused supervisor never gives up on the run", not st.get("gave_up"),
          str(st.get("gave_up")))
    check("the last history entry is classified 'busy'",
          st.get("history") and st["history"][-1].get("kind") == "busy",
          str(st.get("history", [])[-1:]))
    check("nothing was started while the box was refusing", started == [], str(started))

# 13. the refusal is also recognised from the log alone — run_discovery_all runs its OWN
#     preflight and exits 1, not 90, so the return code cannot carry this on its own.
with tempfile.TemporaryDirectory() as tmp:
    m = supervisor(tmp)
    open(m.LOG, "w").write("preflight: free 2623 MB (need 2220)\n"
                           "REFUSING: swap at 95% AND 24000 MB.\n")
    check("a REFUSING line in the tail is read as 'no headroom'",
          m.refused_for_headroom() is True)
    open(m.LOG, "a").write("filler\n" * 200)
    check("an old REFUSING line does not excuse a fresh failure",
          m.refused_for_headroom() is False)


# 14. STRUCTURAL (behaviour cannot reach this — there is no repo function that would run a
#     re-added %-gate): no repo module may branch on swap PERCENT. Percent is display-only.
offenders = []
for sub in ("data", "worker"):
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".py") or fn == os.path.basename(__file__):
            continue
        for i, line in enumerate(open(os.path.join(d, fn), errors="replace"), 1):
            s = line.strip()
            if "swap_pct" in s and (s.startswith("if ") or s.startswith("elif ")
                                    or s.startswith("assert ") or s.startswith("while ")):
                offenders.append(f"{sub}/{fn}:{i}")
check("STRUCTURAL: no repo module branches on swap PERCENT (display only)",
      not offenders, str(offenders))

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES")
    sys.exit(1)
print("preflight resource gate holds: percent never refuses alone")
