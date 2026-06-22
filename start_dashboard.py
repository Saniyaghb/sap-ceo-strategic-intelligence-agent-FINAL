"""
One-command launcher for the SAP Strategic Intelligence Dashboard.

Run from the project root:
    python start_dashboard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from config import AUTO_REFRESH_HOURS, CHROMA_DIR, PROCESSED_DIR, SCHEDULER_STATUS_FILE


ROOT = Path(__file__).resolve().parent

MASTER_FILE = PROCESSED_DIR / "master_data.csv"
CHUNKS_FILE = PROCESSED_DIR / "chunks.csv"
LOCK_FILE = ROOT / ".pipeline.lock"

REFRESH_SECONDS = AUTO_REFRESH_HOURS * 60 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def write_status(**updates) -> None:
    """
    Save scheduler status so the dashboard can display it.
    """

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    status = {}

    if SCHEDULER_STATUS_FILE.exists():
        try:
            status = json.loads(
                SCHEDULER_STATUS_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            status = {}

    status.update(updates)
    status["updated_at"] = iso_now()

    SCHEDULER_STATUS_FILE.write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )


def file_age_seconds(path: Path) -> float | None:
    """
    Return how old a file is in seconds.
    """

    if not path.exists():
        return None

    return time.time() - path.stat().st_mtime


def chroma_has_files() -> bool:
    """
    Check whether ChromaDB folder exists and has files.
    """

    return CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())


def pipeline_is_needed() -> tuple[bool, str]:
    """
    Decide whether pipeline should run before opening the dashboard.
    """

    if not MASTER_FILE.exists():
        return True, "master_data.csv is missing"

    if not CHUNKS_FILE.exists():
        return True, "chunks.csv is missing"

    if not chroma_has_files():
        return True, "ChromaDB index is missing"

    age = file_age_seconds(MASTER_FILE)

    if age is not None and age >= REFRESH_SECONDS:
        hours = round(age / 3600, 2)
        return True, f"processed data is {hours} hours old"

    return False, "processed data is still fresh"


def lock_is_stale() -> bool:
    """
    Prevent two pipelines from running at the same time.
    If the lock is older than 2 hours, assume it is stale.
    """

    if not LOCK_FILE.exists():
        return False

    age = file_age_seconds(LOCK_FILE)

    return age is not None and age > 2 * 60 * 60


def run_pipeline(reason: str) -> bool:
    """
    Run run_pipeline.py safely and write scheduler status.
    """

    if LOCK_FILE.exists() and not lock_is_stale():
        print("Pipeline is already running. Skipping this scheduler cycle.")

        write_status(
            status="skipped",
            reason="Pipeline was already running",
            next_refresh_after_hours=AUTO_REFRESH_HOURS,
        )

        return False

    if LOCK_FILE.exists() and lock_is_stale():
        LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(iso_now(), encoding="utf-8")

    print(f"\nStarting pipeline: {reason}")

    write_status(
        status="running",
        reason=reason,
        started_at=iso_now(),
        next_refresh_after_hours=AUTO_REFRESH_HOURS,
    )

    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "run_pipeline.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60 * 60,
        )

        output = (result.stdout or "") + "\n" + (result.stderr or "")

        if result.returncode == 0:
            print("Pipeline completed successfully.")

            write_status(
                status="success",
                reason=reason,
                last_success_at=iso_now(),
                last_output=output[-4000:],
                next_refresh_after_hours=AUTO_REFRESH_HOURS,
            )

            return True

        print("Pipeline failed. Check scheduler_status.json for logs.")

        write_status(
            status="failed",
            reason=reason,
            last_failure_at=iso_now(),
            last_output=output[-4000:],
            next_refresh_after_hours=AUTO_REFRESH_HOURS,
        )

        return False

    except Exception as exc:
        print(f"Pipeline crashed: {exc}")

        write_status(
            status="failed",
            reason=reason,
            last_failure_at=iso_now(),
            last_output=str(exc),
            next_refresh_after_hours=AUTO_REFRESH_HOURS,
        )

        return False

    finally:
        LOCK_FILE.unlink(missing_ok=True)


def scheduler_loop(stop_event: threading.Event) -> None:
    """
    Refresh pipeline every AUTO_REFRESH_HOURS while Streamlit is running.
    """

    while not stop_event.wait(REFRESH_SECONDS):
        run_pipeline(f"scheduled {AUTO_REFRESH_HOURS}-hour refresh")


def start_streamlit() -> int:
    """
    Start the Streamlit dashboard.
    """

    app_file = ROOT / "dashboard" / "app.py"

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_file),
    ]

    print("\nOpening Streamlit dashboard...")
    print("Command:", " ".join(command))

    return subprocess.call(command, cwd=str(ROOT))


def main() -> None:
    print("SAP Strategic Intelligence Dashboard Launcher")
    print(f"Automatic refresh interval: every {AUTO_REFRESH_HOURS} hours")

    needed, reason = pipeline_is_needed()

    if needed:
        run_pipeline(f"startup refresh because {reason}")
    else:
        print(f"Skipping startup pipeline: {reason}")

        write_status(
            status="ready",
            reason=reason,
            next_refresh_after_hours=AUTO_REFRESH_HOURS,
        )

    stop_event = threading.Event()

    scheduler_thread = threading.Thread(
        target=scheduler_loop,
        args=(stop_event,),
        daemon=True,
    )

    scheduler_thread.start()

    try:
        exit_code = start_streamlit()

        if exit_code != 0:
            print(f"Streamlit exited with code {exit_code}")

    finally:
        stop_event.set()


if __name__ == "__main__":
    main()