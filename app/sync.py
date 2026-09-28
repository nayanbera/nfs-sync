"""rsync execution engine and APScheduler job management."""
import os
import re
import subprocess
import tempfile
import threading
import time
from datetime import datetime

from . import db, scheduler
from .models import SyncJob, SyncRun

_lock    = threading.Lock()
_running = {}   # job_id -> {"run_id": int, "log_path": str}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_running(job_id):
    with _lock:
        return job_id in _running


def running_log_path(job_id):
    with _lock:
        info = _running.get(job_id)
        return info["log_path"] if info else None


def _parse_stats(text):
    files = 0
    nbytes = 0
    m = re.search(r"Number of regular files transferred:\s+([\d,]+)", text)
    if m:
        files = int(m.group(1).replace(",", ""))
    m = re.search(r"Total transferred file size:\s+([\d,]+)", text)
    if m:
        nbytes = int(m.group(1).replace(",", ""))
    return files, nbytes


# ── Core runner ───────────────────────────────────────────────────────────────

def run_job(app, job_id):
    """Execute rsync for the given job. Called by APScheduler or 'Run Now'."""
    with app.app_context():
        job = SyncJob.query.get(job_id)
        if job is None or not job.enabled:
            return

        with _lock:
            if job_id in _running:
                return   # already running

        # Create run record
        run = SyncRun(job_id=job_id, started_at=datetime.utcnow())
        db.session.add(run)
        job.last_status = "running"
        job.last_run_at = datetime.utcnow()
        db.session.commit()

        # Temp log file (overwritten each run; kept until next run)
        log_path = os.path.join(tempfile.gettempdir(), f"nfssync_{job_id}.log")

        with _lock:
            _running[job_id] = {"run_id": run.id, "log_path": log_path}

        # Build rsync command
        cmd = ["rsync", "-a", "--omit-dir-times",
               "--no-perms", "--no-owner", "--no-group",
               "--verbose", "--stats"]
        if job.use_checksum:
            cmd.append("--checksum")
        if job.bwlimit:
            cmd.append(f"--bwlimit={job.bwlimit}")
        src = job.src_path.rstrip("/") + "/"
        cmd += [src, job.dst_path]

        t0 = time.monotonic()
        exit_code = -1
        log_lines = []

        try:
            with open(log_path, "w", buffering=1) as lf:
                lf.write(f"$ {' '.join(cmd)}\n\n")
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    lf.write(line)
                    log_lines.append(line)
                proc.wait()
                exit_code = proc.returncode
        except FileNotFoundError:
            msg = "ERROR: rsync not found — install rsync on this machine.\n"
            with open(log_path, "a") as lf:
                lf.write(msg)
            log_lines.append(msg)
        except Exception as exc:
            msg = f"ERROR: {exc}\n"
            with open(log_path, "a") as lf:
                lf.write(msg)
            log_lines.append(msg)

        duration  = time.monotonic() - t0
        success   = (exit_code == 0)
        full_log  = "".join(log_lines)
        files, nb = _parse_stats(full_log)

        run.finished_at       = datetime.utcnow()
        run.status            = "success" if success else "error"
        run.exit_code         = exit_code
        run.duration_seconds  = duration
        run.files_transferred = files
        run.bytes_transferred = nb
        if not success:
            run.log_text = full_log[-65536:]   # keep last 64 KB

        job.last_status = run.status

        if not success and not job.notified_error:
            job.notified_error = True
            db.session.commit()
            from .notify import send_failure_email
            send_failure_email(app, job, run)
        elif success and job.notified_error:
            job.notified_error = False
            db.session.commit()
            from .notify import send_recovery_email
            send_recovery_email(app, job)
        else:
            db.session.commit()

        with _lock:
            _running.pop(job_id, None)


# ── APScheduler helpers ───────────────────────────────────────────────────────

def schedule_job(app, job):
    """Register or replace an APScheduler job for the given SyncJob."""
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger

    apsjob_id = f"sync_{job.id}"
    try:
        scheduler.remove_job(apsjob_id)
    except Exception:
        pass

    if not job.enabled or job.schedule_type == "manual":
        return

    if job.schedule_type == "interval":
        trigger = IntervalTrigger(**{job.interval_unit: job.interval_value})
    elif job.schedule_type == "daily":
        trigger = CronTrigger(hour=job.cron_hour, minute=job.cron_minute)
    elif job.schedule_type == "weekly":
        trigger = CronTrigger(day_of_week=job.cron_day_of_week,
                              hour=job.cron_hour, minute=job.cron_minute)
    elif job.schedule_type == "monthly":
        trigger = CronTrigger(day=job.cron_day,
                              hour=job.cron_hour, minute=job.cron_minute)
    else:
        return

    scheduler.add_job(
        run_job,
        trigger,
        args=[app, job.id],
        id=apsjob_id,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=300,
    )


def unschedule_job(job_id):
    try:
        scheduler.remove_job(f"sync_{job_id}")
    except Exception:
        pass


def next_run_time(job_id):
    """Return the next scheduled run datetime, or None."""
    try:
        apsjob = scheduler.get_job(f"sync_{job_id}")
        return apsjob.next_run_time if apsjob else None
    except Exception:
        return None


def load_all_jobs(app):
    """Called at startup to restore scheduled jobs from the database."""
    with app.app_context():
        for job in SyncJob.query.filter_by(enabled=True).all():
            if job.schedule_type != "manual":
                schedule_job(app, job)
