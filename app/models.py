from datetime import datetime
from flask_login import UserMixin
from . import db


# ── Admin user (single, stored in SystemConfig) ───────────────────────────────

class AdminUser(UserMixin):
    """Lightweight user object for Flask-Login. Always id='admin'."""
    id = "admin"


# ── Key/value config store ────────────────────────────────────────────────────

class SystemConfig(db.Model):
    __tablename__ = "system_config"
    key   = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, default="")

    @classmethod
    def get(cls, key, default=""):
        row = cls.query.get(key)
        return row.value if row else default

    @classmethod
    def set(cls, key, value):
        row = cls.query.get(key)
        if row:
            row.value = str(value)
        else:
            db.session.add(cls(key=key, value=str(value)))
        db.session.commit()


# ── Sync job definition ───────────────────────────────────────────────────────

class SyncJob(db.Model):
    __tablename__ = "sync_job"
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(128), nullable=False)
    src_path       = db.Column(db.String(512), nullable=False)
    dst_path       = db.Column(db.String(512), nullable=False)
    # schedule_type: "manual" | "interval" | "daily"
    schedule_type  = db.Column(db.String(16), default="manual")
    interval_value = db.Column(db.Integer, default=1)
    # interval_unit: "minutes" | "hours" | "days" | "weeks"
    interval_unit  = db.Column(db.String(16), default="hours")
    cron_hour      = db.Column(db.Integer, default=2)
    cron_minute    = db.Column(db.Integer, default=0)
    bwlimit        = db.Column(db.Integer, default=0)   # KB/s; 0 = unlimited
    use_checksum   = db.Column(db.Boolean, default=False)
    enabled        = db.Column(db.Boolean, default=True)
    last_run_at    = db.Column(db.DateTime)
    last_status    = db.Column(db.String(16), default="never")
    # True once a failure email has been sent; cleared on next success
    notified_error = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    runs           = db.relationship(
        "SyncRun", backref="job", lazy="dynamic",
        cascade="all, delete-orphan",
    )


# ── Run history ───────────────────────────────────────────────────────────────

class SyncRun(db.Model):
    __tablename__ = "sync_run"
    id                = db.Column(db.Integer, primary_key=True)
    job_id            = db.Column(db.Integer, db.ForeignKey("sync_job.id"), nullable=False)
    started_at        = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at       = db.Column(db.DateTime)
    # status: "running" | "success" | "error"
    status            = db.Column(db.String(16), default="running")
    exit_code         = db.Column(db.Integer)
    log_text          = db.Column(db.Text)   # stored only for failed runs
    files_transferred = db.Column(db.Integer, default=0)
    bytes_transferred = db.Column(db.Integer, default=0)
    duration_seconds  = db.Column(db.Float)

    @property
    def duration_str(self):
        if self.duration_seconds is None:
            return "—"
        s = int(self.duration_seconds)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m"

    @property
    def size_str(self):
        b = self.bytes_transferred or 0
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
