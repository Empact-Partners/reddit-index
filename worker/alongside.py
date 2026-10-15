#!/usr/bin/env python3
"""Labelling beside a daytime pass's collection (decision 0037).

Until 15 Oct a daytime pass collected, then labelled: for the last 45 minutes of its 330 nobody called Reddit, and
since the shared Reddit app became the bound on collection (decision 0035's first day: other users took 67% of its
calls) those minutes were collection lost. Labelling needs GLM, Jev and the database, never Reddit, so it runs here,
in its own thread and on its own database connection, while collection runs; collection then goes on until 15 minutes
before the pass ends, and the pass's own classify stage takes what is left.

The thread runs worker/classify_sweep.run in rounds. A round labels what is in the queue; a round that found nothing
waits `pause_s` for collection to add more. It stops when told (collection ended), at its deadline, when the stop
switch is off, when a round reports an error (GLM or Jev down: the pass's own stage tries again), or when the pass's
allowances (GLM credits, Jev dollars, items) are used. It never touches the pass's own connection: a statement there
would land inside collection's open transaction.
"""
from __future__ import annotations

import threading
import time

SUM_KEYS = ("labelled", "rejected", "not_checked", "jev_decided", "glm_decided", "jev_usd", "glm_credits", "read_bytes",
            "gone_from_queue")


class Alongside:
    def __init__(self, connect, run_fn, cfg: dict, deadline: float, log=print, pause_s: float = 120.0,
                 switch=None, halt: threading.Event | None = None):
        """connect(): a new database connection. run_fn: classify_sweep.run. cfg: the classify config, whose
        glm_credits_max, jev_usd_max and max_items are the pass's allowances for the thread and the stage together.
        switch(conn): a reason to stop (the stop switch off), or None. halt: set by the pass's main thread when it
        meets the egress line or its own estimate cap (Run.stop_reason); the thread stops at its next batch."""
        self.connect, self.run_fn, self.cfg, self.deadline = connect, run_fn, dict(cfg), deadline
        self.log, self.pause_s, self.switch = log, pause_s, switch
        self.halt = halt or threading.Event()
        self._stop = threading.Event()
        self._conn = None
        self.recs: list[dict] = []
        self.error: str | None = None
        self.ended: str | None = None
        self._t = threading.Thread(target=self._loop, name="label-alongside", daemon=True)

    def start(self) -> "Alongside":
        self._t.start()
        return self

    def used(self) -> dict:
        return {k: sum(float(r.get(k) or 0) for r in self.recs) for k in SUM_KEYS}

    def left(self) -> dict:
        """The classify config with what the thread has already spent taken off its allowances."""
        u = self.used()
        out = dict(self.cfg)
        out["glm_credits_max"] = max(0.0, float(self.cfg.get("glm_credits_max", 3000)) - u["glm_credits"])
        out["jev_usd_max"] = max(0.0, float(self.cfg.get("jev_usd_max", 1.0)) - u["jev_usd"])
        out["max_items"] = max(0, int(self.cfg.get("max_items", 60000))
                               - int(u["labelled"] + u["rejected"] + u["not_checked"]))
        return out

    def _loop(self) -> None:
        conn = None
        try:
            conn = self.connect()
            conn.autocommit = True
            self._conn = conn
            while not self._stop.is_set():
                if self.halt.is_set():
                    self.ended = "the pass stopped for egress"
                    break
                if time.time() >= self.deadline:
                    self.ended = "its deadline"
                    break
                why = self.switch(conn) if self.switch else None
                if why:
                    self.ended = why
                    break
                cfg = self.left()
                if cfg["glm_credits_max"] <= 0 or cfg["jev_usd_max"] <= 0 or cfg["max_items"] <= 0:
                    self.ended = "the pass's labelling allowance is used"
                    break
                rec = self.run_fn(conn, cfg, self.deadline, should_stop=self._should_stop, log=self.log)
                self.recs.append(rec)
                if rec.get("error"):
                    self.error = rec["error"]
                    self.ended = "a round failed: the pass's own classify stage tries again"
                    break
                if not (rec.get("labelled") or rec.get("rejected")):
                    self._stop.wait(self.pause_s)   # nothing to label yet: let collection add some
                    if self.halt.is_set():
                        self.ended = "the pass stopped for egress"
                        break
        except Exception as e:  # noqa: BLE001 - on the receipt; the pass's own classify stage still runs
            self.error = f"{type(e).__name__}: {str(e)[:200]}"
            self.ended = "it failed"
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass

    def _should_stop(self) -> str | None:
        if self.halt.is_set():
            return "the pass stopped for egress"
        return "collection ended" if self._stop.is_set() else None

    def finish(self, timeout: float = 1200.0) -> dict:
        """Tell the thread collection has ended, wait for its round to end (a GLM job may take its 15 minutes), and
        return what it did. A thread still alive after that is fenced: its query cancelled and its connection closed,
        so nothing it does can land after the pass's receipt (review, 15 Oct)."""
        self._stop.set()
        self._t.join(timeout)
        if self._t.is_alive() and self._conn is not None:
            for f in ("cancel", "close"):
                try:
                    getattr(self._conn, f)()
                except Exception:  # noqa: BLE001
                    pass
            self._t.join(60)
        out = {k: (round(v, 4) if k in ("jev_usd", "glm_credits") else int(v)) for k, v in self.used().items()}
        out["rounds"] = len(self.recs)
        out["ended"] = self.ended or ("collection ended" if not self._t.is_alive() else "still running at the join")
        if self.error:
            out["error"] = self.error
        last = next((r.get("allowance_used") for r in reversed(self.recs) if r.get("allowance_used")), None)
        if last:
            out["last_allowance"] = last
        return out
