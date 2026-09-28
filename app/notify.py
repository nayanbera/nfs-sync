"""Email notifications for sync job failures and recoveries."""
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _smtp_cfg(app):
    from .models import SystemConfig
    with app.app_context():
        return {
            "host":     SystemConfig.get("smtp_host"),
            "port":     int(SystemConfig.get("smtp_port", "587")),
            "user":     SystemConfig.get("smtp_user"),
            "password": SystemConfig.get("smtp_password"),
            "from":     SystemConfig.get("smtp_from"),
            "to":       SystemConfig.get("notify_email"),
            "tls":      SystemConfig.get("smtp_tls", "1") == "1",
        }


def _send(app, subject, body):
    cfg = _smtp_cfg(app)
    if not cfg["host"] or not cfg["to"]:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["from"] or cfg["user"]
        msg["To"]      = cfg["to"]
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
            if cfg["tls"]:
                s.starttls()
            if cfg["user"]:
                s.login(cfg["user"], cfg["password"])
            s.sendmail(msg["From"], [cfg["to"]], msg.as_string())
    except Exception:
        traceback.print_exc()


def send_failure_email(app, job, run):
    from .models import SystemConfig
    with app.app_context():
        base_url = SystemConfig.get("base_url", "http://localhost:5050")
    log_url = f"{base_url.rstrip('/')}/jobs/{job.id}/runs/{run.id}/log"
    subject = f"[NFS Sync] FAILED: {job.name}"
    body = (
        f"Sync job '{job.name}' failed.\n\n"
        f"  Source : {job.src_path}\n"
        f"  Dest   : {job.dst_path}\n"
        f"  Started: {run.started_at}\n"
        f"  Exit   : {run.exit_code}\n\n"
        f"View the error log:\n  {log_url}\n"
    )
    _send(app, subject, body)


def send_recovery_email(app, job):
    subject = f"[NFS Sync] Recovered: {job.name}"
    body = (
        f"Sync job '{job.name}' completed successfully after a previous failure.\n\n"
        f"  Source : {job.src_path}\n"
        f"  Dest   : {job.dst_path}\n"
    )
    _send(app, subject, body)
