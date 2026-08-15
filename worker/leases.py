#!/usr/bin/env python3
"""Work claims via flock — crash-safe by construction.

Why flock and not a TTL lease file: the kernel releases the lock when the
holder dies, for any reason, including kill -9, panic and power loss. There is
no reaper to write, no TTL window during which a dead process still owns work,
and no reap race — the classic bug where two processes both decide a stale
lease is free and both recreate it. (classify_codex.burn_lock has exactly that
race today and survives only because there is ever one burner.)

BSD flock on macOS is per open file DESCRIPTION, so it also excludes threads
inside one process that open their own fd. One primitive covers both.

The JSON body is observability only — never correctness. A heartbeat that has
gone quiet means "alive but stuck", which is a supervisor decision, not a
lock decision.
"""
import errno
import fcntl
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LEASE_DIR = os.path.join(HERE, ".cache", "leases")
os.makedirs(LEASE_DIR, exist_ok=True)


def _path(key):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return os.path.join(LEASE_DIR, f"{safe}.lock")


class Lease:
    """Exclusive claim on one work key. Use as a context manager or acquire()."""

    def __init__(self, key):
        self.key = key
        self.fp = _path(key)
        self.fd = None

    def acquire(self):
        fd = os.open(self.fp, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            os.close(fd)
            if e.errno in (errno.EAGAIN, errno.EACCES):
                return False
            raise
        self.fd = fd
        self.beat(since=time.time())
        return True

    def beat(self, **fields):
        if self.fd is None:
            return
        body = {"key": self.key, "pid": os.getpid(), "last_beat": time.time()}
        body.update(fields)
        try:
            os.lseek(self.fd, 0, os.SEEK_SET)
            os.ftruncate(self.fd, 0)
            os.write(self.fd, json.dumps(body).encode())
            os.fsync(self.fd)
        except OSError:
            pass

    def release(self):
        if self.fd is None:
            return
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None

    def __enter__(self):
        return self if self.acquire() else None

    def __exit__(self, *_):
        self.release()


def is_held(key):
    """True when someone holds this key right now. Probe, never a claim."""
    fp = _path(key)
    if not os.path.exists(fp):
        return False
    fd = os.open(fp, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def scan():
    """key -> body for every lease file, with `held` from a live probe."""
    out = {}
    for fn in os.listdir(LEASE_DIR):
        if not fn.endswith(".lock"):
            continue
        fp = os.path.join(LEASE_DIR, fn)
        try:
            body = json.loads(open(fp).read() or "{}")
        except Exception:
            body = {}
        key = body.get("key", fn[:-5])
        body["held"] = is_held(key)
        out[key] = body
    return out


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        a, b = Lease("selftest-key"), Lease("selftest-key")
        assert a.acquire(), "first acquire must succeed"
        assert not b.acquire(), "second acquire must be refused"
        assert is_held("selftest-key")
        a.release()
        assert not is_held("selftest-key"), "release must free the key"
        assert b.acquire(), "acquire after release must succeed"
        b.release()
        os.remove(_path("selftest-key"))
        print("leases selftest OK: exclusion, probe, release")
    else:
        for k, v in sorted(scan().items()):
            age = time.time() - (v.get("last_beat") or 0)
            print(f"{'HELD' if v.get('held') else 'free'}  {k:34} pid={v.get('pid')} "
                  f"beat={age:.0f}s ago  {v.get('note','')}")
