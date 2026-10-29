"""Log file, stage messages and progress with ETA for the HCMRE-Q v2 scripts.

    import runlog
    runlog.run("eval_benchmark", main)            # runs main(); everything printed also goes to logs/eval_benchmark_<time>.log
    runlog.stage("D3 split-half stability")       # [10:31:02 +00:01:25] == D3 split-half stability
    for q in runlog.progress(queries, "systems"): # one line about every 5% or 20 s, with the time left

The log starts with the command, the working directory, Python, the git commit and the sha256 of the main input
files, and ends with OK or FAILED and the run time. Logs go to Evaluation/hcmre_q_v2/logs/ (HCMRE_LOG_DIR to
change it; HCMRE_NO_LOG=1 to switch the file off, e.g. in sub-processes). Only messages are added: the files a
script writes are byte-for-byte the same as without logging.
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = ["data/queries.jsonl", "data/qrels.tsv", "data/corpus_attributes.csv", "../../Data/v3/master_v3.csv"]


def _hms(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class _Tee:
    def __init__(self, stream, fh):
        self.stream, self.fh = stream, fh

    def write(self, text):
        self.stream.write(text)
        self.fh.write(text.replace("\r", "\n"))
        self.fh.flush()
        return len(text)

    def flush(self):
        self.stream.flush()
        self.fh.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


class RunLog:
    def __init__(self, name: str, path: Path | None):
        self.name, self.path, self.t0, self.ok = name, path, time.time(), False

    def stamp(self) -> str:
        return f"[{datetime.now():%H:%M:%S} +{_hms(time.time() - self.t0)}]"

    def stage(self, msg: str):
        print(f"{self.stamp()} == {msg}", flush=True)

    def info(self, msg: str):
        print(f"{self.stamp()} {msg}", flush=True)

    def progress(self, items, label: str, total: int | None = None, every_s: float = 20.0, every_frac: float = 0.05):
        """Yield the items; print 'label i/n (p%), elapsed, time left' about every 5% or every_s seconds."""
        n = total if total is not None else len(items)
        start = last = time.time()
        step = max(1, int(n * every_frac))
        i = 0
        for i, item in enumerate(items, 1):
            yield item
            now = time.time()
            if i == n or i % step == 0 or now - last >= every_s:
                rate = (now - start) / i
                print(f"{self.stamp()}    {label} {i}/{n} ({100 * i / n:.0f}%), {rate:.2f} s/item, "
                      f"left ~{_hms(rate * (n - i))}", flush=True)
                last = now


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _git() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True,
                             timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, capture_output=True, text=True,
                               timeout=10).stdout.strip()
        return f"{rev}{' (uncommitted changes in Evaluation/hcmre_q_v2)' if dirty else ''}" if rev else "n/a"
    except (OSError, subprocess.SubprocessError):
        return "n/a"


_LOG = RunLog("run", None)


def stage(msg: str):
    _LOG.stage(msg)


def info(msg: str):
    _LOG.info(msg)


def progress(items, label: str, total: int | None = None, every_s: float = 20.0, every_frac: float = 0.05):
    return _LOG.progress(items, label, total, every_s, every_frac)


def start(name: str) -> RunLog:
    """Tee stdout/stderr to a new log file and print the run header."""
    global _LOG
    path = None
    if os.environ.get("HCMRE_NO_LOG") != "1":
        log_dir = Path(os.environ.get("HCMRE_LOG_DIR", HERE / "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{name}_{datetime.now():%Y%m%d-%H%M%S}.log"
        fh = open(path, "a", encoding="utf-8")
        sys.stdout, sys.stderr = _Tee(sys.stdout, fh), _Tee(sys.stderr, fh)
    _LOG = RunLog(name, path)
    print(f"===== {name} — started {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"command : {' '.join([Path(sys.executable).name, *sys.argv])}")
    print(f"cwd     : {os.getcwd()}")
    print(f"python  : {platform.python_version()} on {platform.platform()}; "
          f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED', 'unset')}")
    print(f"git     : {_git()}")
    for rel in INPUTS:
        p = (HERE / rel).resolve()
        if p.exists():
            print(f"input   : {rel}  sha256 {_sha(p)}…")
    if path:
        print(f"log file: {path}")
    print(flush=True)
    return _LOG


def run(name: str, fn):
    """start(name), call fn(), and end the log with OK / FAILED and the run time."""
    log = start(name)
    end = lambda status: print(f"===== {name} — {status}, finished {datetime.now():%Y-%m-%d %H:%M:%S}, "
                               f"run time {_hms(time.time() - log.t0)}", flush=True)
    try:
        result = fn()
    except SystemExit as exc:
        code = exc.code
        if code not in (0, None):
            end(f"FAILED ({code if isinstance(code, int) else 'exit code 1: ' + str(code)})")
        else:
            end("OK")
        raise
    except BaseException as exc:
        traceback.print_exc()
        end(f"FAILED ({type(exc).__name__}: {exc})")
        raise SystemExit(1)
    end("OK")
    return result
