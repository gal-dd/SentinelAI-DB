"""Read and publish checkpoint state as one verified Git commit."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import os
import re
import subprocess
from tempfile import NamedTemporaryFile

from .core import (PLAN, ROOT, check_quotas, export_rows, json_bytes, jsonl_bytes,
                   load_saved, metadata_rows, read_json)

BRANCH = "poc/security-classification-dataset"
CHECKPOINT_SIZE = PLAN["checkpoint_size"]
FINAL_NAME = "synthetic_security_classification_100k.json"
PILOT_DATA = Path("data/pilot/pilot.jsonl")
PILOT_META = Path("metadata/pilot/pilot.jsonl")
PILOT_REPORT = Path("reports/pilot/quality.json")
PROGRESS = Path("progress.json")


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def payload_sha(content):
    return sha256(content).hexdigest()


def load_pilot(root=ROOT):
    rows = load_saved(root / PILOT_DATA, root / PILOT_META, 1)
    check_quotas(rows, "pilot")
    report = read_json(root / PILOT_REPORT)
    expected = {PILOT_DATA.as_posix(): file_sha(root / PILOT_DATA),
                PILOT_META.as_posix(): file_sha(root / PILOT_META)}
    if report["schema"] != "passed" or report["semantic"]["status"] != "completed":
        raise ValueError("Pilot quality checks are incomplete")
    if report["data_hashes"] != expected:
        raise ValueError("Pilot data or metadata differs from its report")
    return rows


def pilot_hashes(root=ROOT):
    paths = (PILOT_DATA, PILOT_META, PILOT_REPORT, Path("reports/pilot/review.md"),
             Path("config/plan.json"), Path(f"policy/v{PLAN['policy_version']}.md"),
             Path(f"prompts/v{PLAN['prompt_version']}.md"))
    return {path.as_posix(): file_sha(root / path) for path in paths}


def initial_state(root=ROOT):
    return {"policy_version": PLAN["policy_version"], "prompt_version": PLAN["prompt_version"],
            "pilot_records": len(load_pilot(root)), "pilot_hashes": pilot_hashes(root),
            "pilot_quality": "completed", "production_records": 0, "last_checkpoint": 0,
            "next_id": 1, "checkpoints": [], "final": None}


def batch_paths(index):
    return (
        Path(f"data/checkpoints/batch-{index:04d}.jsonl"),
        Path(f"metadata/checkpoints/batch-{index:04d}.jsonl"),
        Path(f"reports/checkpoints/batch-{index:04d}.json"),
    )


def load_progress(root=ROOT):
    state = read_json(root / PROGRESS)
    base = initial_state(root)
    for key in ("pilot_records", "pilot_hashes", "pilot_quality", "policy_version", "prompt_version"):
        if state[key] != base[key]:
            raise ValueError(f"Invalid progress metadata: {key}")
    production = []
    expected_paths = set()
    if state["last_checkpoint"] != len(state["checkpoints"]):
        raise ValueError("Checkpoint count mismatch")
    for index, batch in enumerate(state["checkpoints"], 1):
        paths = batch_paths(index)
        start = (index - 1) * CHECKPOINT_SIZE + 1
        if (batch["checkpoint"], batch["start_id"], batch["end_id"]) != (index, start, start + CHECKPOINT_SIZE - 1):
            raise ValueError(f"Invalid checkpoint range: {index}")
        expected_paths.update(paths)
        if batch["sha256"] != {path.as_posix(): file_sha(root / path) for path in paths}:
            raise ValueError(f"Checksum mismatch in checkpoint {index}")
        rows = load_saved(root / paths[0], root / paths[1], start)
        if len(rows) != CHECKPOINT_SIZE:
            raise ValueError(f"Incorrect checkpoint size: {index}")
        report = read_json(root / paths[2])
        if report["metrics"]["records"] != len(rows) or report["semantic"]["status"] != "completed":
            raise ValueError(f"Invalid checkpoint quality report: {index}")
        production.extend(rows)
    for folder, extension in (("data", "jsonl"), ("metadata", "jsonl"), ("reports", "json")):
        for path in (root / folder / "checkpoints").glob(f"batch-*.{extension}"):
            if path.relative_to(root) not in expected_paths:
                raise ValueError(f"Checkpoint file not recorded in progress: {path}")
    if state["production_records"] != len(production) or state["next_id"] != len(production) + 1:
        raise ValueError("Progress counts do not match checkpoint files")
    check_quotas(production, "production", final=bool(state["final"]))
    if state["final"]:
        paths = (Path(FINAL_NAME), Path("reports/final.json"))
        if state["final"] != {path.as_posix(): file_sha(root / path) for path in paths}:
            raise ValueError("Final artifact or report checksum mismatch")
        if read_json(root / paths[0]) != export_rows(production):
            raise ValueError("Final artifact differs from the checkpoint records")
    return state, production


def handoff(state):
    count = state["production_records"]
    last = state["last_checkpoint"]
    final_status = "נוצר ואומת" if state["final"] else "ממתין להשלמת הייצור"
    last_note = (f"[`batch-{last:04d}`]({batch_paths(last)[2].as_posix()})"
                 if last else "טרם נוצרה מנת ייצור")
    return f"""# המשך עבודה

מטרת הריפו היא ליצור 100,000 רשומות בעברית לאימון מודל סיווג רגישות ניסויי עם ארבע רמות מאוזנות. ענף העבודה הוא `{BRANCH}`.

| פריט | מצב |
|---|---|
| מדיניות | [v{PLAN["policy_version"]}](policy/v{PLAN["policy_version"]}.md) |
| פרומפט | [v{PLAN["prompt_version"]}](prompts/v{PLAN["prompt_version"]}.md) |
| פיילוט | {state["pilot_records"]} רשומות הערכה, בדיקות איכות הושלמו |
| ייצור | {count:,} / 100,000 |
| מנת ייצור אחרונה | {last_note} |
| מזהה הייצור הבא | {state["next_id"]} |
| JSON סופי | {final_status} |

`data/` שומר רשומות. `metadata/` שומר מקור, תרחיש, נימוק וביקורת. `reports/` שומר תוצאות איכות. `config/` כולל מכסות, תרחישים ומקורות. `progress.json` כולל טווחי מזהים ובדיקות SHA-256. כל מנה ומצב ההתקדמות שלה נכנסים לאותו commit.

1. פתח checkout נקי של ענף העבודה והריץ `python -m sentinel_dataset verify`.
2. קרא [מדיניות](policy/v{PLAN["policy_version"]}.md), [דוח פיילוט](reports/pilot/review.md) ואת [הוראות ההפעלה](README.md). בדיקות הפיילוט הושלמו ואפשר להמשיך ישירות לייצור בכפוף לבדיקות האיכות.
3. הכן תרחישים ומקורות מגוונים, חבר את הטקסטים באמצעות GPT בסביבת Work, צבור 500 תקינים והריץ את הבדיקות והביקורת. שמור כל מנה דרך `checkpoint` ואמת את ראש הענף המרוחק.
4. אם commit מקומי טרם הועלה, הרץ `python -m sentinel_dataset publish` מאותו checkout. אם לא קיימת סביבת הריצה הקודמת, המשך מהמנה האחרונה שמופיעה בענף המרוחק.
5. עם השלמת המכסות הרץ `finalize` לבדיקת המאגר ולבניית קובץ האימון.

לפני כתיבת מנה נוספת, השווה את התפלגות האורכים, המקורות והסיווגים המצטברת למכסות ב־`config/plan.json`. דוח המנה האחרונה מפרט את כיסוי ביקורת התיוג ואת סוג הביקורת. מגבלות שנצפו בפיילוט מופיעות ב[דוח הביקורת](reports/pilot/review.md). במהלך הייצור יש להרחיב את קבוצות המקור הציבורי ולבדוק תלות של תוויות במונחים, בנושא ובפורמט. אפשר להמשיך דרך Work ללא API חיצוני. מגבלת הקשר ותקציב הפלט מחייבת להסתמך על ה־checkpoint המרוחק בהמשך בין שיחות. דוגמאות הפיילוט משמשות להערכה ולסינון כפילויות בלבד.
"""


def batch_artifacts(state, rows, metrics, review, packet, decisions):
    index = state["last_checkpoint"] + 1
    start = state["next_id"]
    end = start + len(rows) - 1
    data, meta, quality = batch_paths(index)
    data_bytes = jsonl_bytes(export_rows(rows, start))
    meta_bytes = jsonl_bytes(metadata_rows(rows, start, decisions["records"], packet["alerts"]))
    report = {
        "checkpoint": index, "start_id": start, "end_id": end,
        "policy_version": PLAN["policy_version"], "prompt_version": PLAN["prompt_version"],
        "metrics": metrics, "schema": "passed", "normalized_exact_duplicates": 0,
        "semantic": packet["semantic"], "similarity_alerts": packet["alerts"], "review": review,
    }
    files = {data: data_bytes, meta: meta_bytes, quality: json_bytes(report)}
    state["checkpoints"].append({
        "checkpoint": index, "start_id": start, "end_id": end,
        "sha256": {path.as_posix(): payload_sha(content) for path, content in files.items()},
    })
    state.update(last_checkpoint=index, production_records=end, next_id=end + 1)
    return files


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise ValueError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def remote_head(remote):
    result = git("ls-remote", "--exit-code", "--heads", remote, f"refs/heads/{BRANCH}")
    sha, ref = result.split("\t")
    if ref != f"refs/heads/{BRANCH}" or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Unexpected remote branch reference")
    return sha


def preflight(remote, require_equal=True):
    if git("branch", "--show-current") != BRANCH:
        raise ValueError(f"Check out {BRANCH}")
    if git("status", "--porcelain"):
        raise ValueError("Use a clean checkout; store input files under .poc-local/")
    local, upstream = git("rev-parse", "HEAD"), remote_head(remote)
    if require_equal and local != upstream:
        raise ValueError("Local and remote branch differ. Inspect the commits before creating a checkpoint.")
    return local, upstream


@contextmanager
def checkpoint_lock():
    path = Path(git("rev-parse", "--absolute-git-dir")) / "sentinel-dataset.lock"
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            lock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            lock = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            lock()
        except OSError as error:
            raise ValueError("A dataset publication is already running in this checkout") from error
        yield


def write_file(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(contents)
        temp = Path(stream.name)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def state_artifacts(files, state):
    return {**files, PROGRESS: json_bytes(state), Path("HANDOFF.md"): handoff(state).encode()}


def commit_state(files, state, message, remote, expected_head):
    if preflight(remote)[0] != expected_head:
        raise ValueError("Branch advanced during preparation. Rebuild against the current checkpoint.")
    files = state_artifacts(files, state)
    for path, content in files.items():
        write_file(ROOT / path, content)
    load_progress()
    git("add", "--", *(path.as_posix() for path in files))
    git("commit", "-m", message)
    return publish(remote)


def publish(remote):
    local, upstream = preflight(remote, require_equal=False)
    load_progress()
    if local != upstream:
        git("merge-base", "--is-ancestor", upstream, local)
        git("push", remote, f"HEAD:refs/heads/{BRANCH}")
    if remote_head(remote) != local:
        raise ValueError("Remote branch does not match the local commit after push")
    return local
