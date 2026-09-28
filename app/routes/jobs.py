import os
import threading
import time

from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, Response, current_app, stream_with_context)
from flask_login import login_required

from .. import db
from ..models import SyncJob, SyncRun
from ..sync import (run_job, schedule_job, unschedule_job,
                    next_run_time, is_running, running_log_path)

jobs_bp = Blueprint("jobs", __name__)


# ── Job list ──────────────────────────────────────────────────────────────────

@jobs_bp.route("/")
@login_required
def list_jobs():
    jobs = SyncJob.query.order_by(SyncJob.name).all()
    next_runs = {j.id: next_run_time(j.id) for j in jobs}
    running   = {j.id: is_running(j.id) for j in jobs}
    return render_template("jobs/list.html",
                           jobs=jobs, next_runs=next_runs, running=running)


# ── Create / Edit ─────────────────────────────────────────────────────────────

@jobs_bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
def new_job():
    if request.method == "POST":
        job = SyncJob()
        _apply_form(job, request.form)
        db.session.add(job)
        db.session.commit()
        schedule_job(current_app._get_current_object(), job)
        flash(f"Job '{job.name}' created.", "success")
        return redirect(url_for("jobs.list_jobs"))
    return render_template("jobs/form.html", job=None, title="New Sync Job")


@jobs_bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    job = SyncJob.query.get_or_404(job_id)
    if request.method == "POST":
        _apply_form(job, request.form)
        db.session.commit()
        unschedule_job(job_id)
        schedule_job(current_app._get_current_object(), job)
        flash(f"Job '{job.name}' updated.", "success")
        return redirect(url_for("jobs.list_jobs"))
    return render_template("jobs/form.html", job=job, title=f"Edit — {job.name}")


def _apply_form(job, form):
    job.name           = form["name"].strip()
    job.src_path       = form["src_path"].strip()
    job.dst_path       = form["dst_path"].strip()
    job.schedule_type  = form.get("schedule_type", "manual")
    job.interval_value = int(form.get("interval_value") or 1)
    job.interval_unit  = form.get("interval_unit", "hours")
    job.cron_hour      = int(form.get("cron_hour") or 2)
    job.cron_minute    = int(form.get("cron_minute") or 0)
    job.bwlimit        = int(form.get("bwlimit") or 0)
    job.enabled        = bool(form.get("enabled"))


# ── Delete ────────────────────────────────────────────────────────────────────

@jobs_bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def delete_job(job_id):
    job = SyncJob.query.get_or_404(job_id)
    unschedule_job(job_id)
    db.session.delete(job)
    db.session.commit()
    flash(f"Job '{job.name}' deleted.", "success")
    return redirect(url_for("jobs.list_jobs"))


# ── Run now ───────────────────────────────────────────────────────────────────

@jobs_bp.route("/jobs/<int:job_id>/run", methods=["POST"])
@login_required
def run_now(job_id):
    job = SyncJob.query.get_or_404(job_id)
    if is_running(job_id):
        flash(f"Job '{job.name}' is already running.", "warning")
        return redirect(url_for("jobs.list_jobs"))
    app = current_app._get_current_object()
    t = threading.Thread(target=run_job, args=(app, job_id), daemon=True)
    t.start()
    time.sleep(0.3)   # brief pause so the run record is created before redirect
    return redirect(url_for("jobs.live_log", job_id=job_id))


# ── Live log (SSE) ────────────────────────────────────────────────────────────

@jobs_bp.route("/jobs/<int:job_id>/live")
@login_required
def live_log(job_id):
    job = SyncJob.query.get_or_404(job_id)
    return render_template("jobs/live.html", job=job)


@jobs_bp.route("/jobs/<int:job_id>/stream")
@login_required
def stream(job_id):
    """Server-Sent Events endpoint — tails the live rsync log file."""
    @stream_with_context
    def generate():
        # Wait briefly for the log file to appear
        log_path = None
        for _ in range(20):
            log_path = running_log_path(job_id)
            if log_path and os.path.exists(log_path):
                break
            time.sleep(0.1)

        if not log_path or not os.path.exists(log_path):
            yield "data: [no log file found]\n\ndata: [DONE]\n\n"
            return

        with open(log_path, "r") as f:
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    if not is_running(job_id):
                        yield "data: [DONE]\n\n"
                        break
                    time.sleep(0.1)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ── Run history ───────────────────────────────────────────────────────────────

@jobs_bp.route("/jobs/<int:job_id>/runs")
@login_required
def run_history(job_id):
    job  = SyncJob.query.get_or_404(job_id)
    runs = (SyncRun.query
            .filter_by(job_id=job_id)
            .order_by(SyncRun.started_at.desc())
            .limit(200)
            .all())
    return render_template("jobs/runs.html", job=job, runs=runs)


@jobs_bp.route("/jobs/<int:job_id>/runs/<int:run_id>/log")
@login_required
def run_log(job_id, run_id):
    job = SyncJob.query.get_or_404(job_id)
    run = SyncRun.query.filter_by(id=run_id, job_id=job_id).first_or_404()
    return render_template("jobs/log.html", job=job, run=run)
