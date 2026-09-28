import atexit

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

db           = SQLAlchemy()
login_manager = LoginManager()
scheduler    = BackgroundScheduler(timezone="UTC")


def create_app():
    app = Flask(__name__)
    from .config import Config
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from .models import AdminUser
        return AdminUser() if user_id == "admin" else None

    with app.app_context():
        from . import models          # noqa: F401  register models
        db.create_all()
        _migrate_schema()
        _seed_defaults()
        _reset_stale_runs()
        from .sync import load_all_jobs
        load_all_jobs(app)

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))

    from .routes.auth     import auth_bp
    from .routes.jobs     import jobs_bp
    from .routes.settings import settings_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(settings_bp)

    _register_filters(app)

    return app


def _register_filters(app):
    """Jinja2 filter: convert a naive UTC datetime to the configured timezone."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    @app.template_filter("localdt")
    def localdt_filter(dt, fmt="%Y-%m-%d %H:%M"):
        if dt is None:
            return "—"
        from datetime import timezone
        from .models import SystemConfig
        tz_name = SystemConfig.get("timezone", "America/Chicago")
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("America/Chicago")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).strftime(fmt)


def _reset_stale_runs():
    """On startup, mark any jobs/runs stuck in 'running' state as failed.

    These are left over from a previous crash or unclean shutdown — they
    cannot actually be running since the app process just started.
    """
    from datetime import datetime
    from .models import SyncJob, SyncRun
    stale_runs = SyncRun.query.filter_by(status="running").all()
    for run in stale_runs:
        run.status = "error"
        run.finished_at = run.finished_at or datetime.utcnow()
        run.log_text = (run.log_text or "") + "\n[Marked failed: app restarted while job was running]"
    stale_jobs = SyncJob.query.filter_by(last_status="running").all()
    for job in stale_jobs:
        job.last_status = "error"
    db.session.commit()


def _migrate_schema():
    """Add columns present in models but missing from the live SQLite database.

    Safe to run on every startup — skips columns that already exist.
    Handles the common case where a pip upgrade adds new model fields.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    for table in db.metadata.tables.values():
        if not inspector.has_table(table.name):
            continue  # db.create_all() already handles brand-new tables
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            sql_default = _col_default_sql(col)
            type_str = str(col.type)
            db.session.execute(
                text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {type_str}{sql_default}")
            )
    db.session.commit()


def _col_default_sql(col):
    """Return a SQL DEFAULT clause for use in ALTER TABLE ADD COLUMN."""
    if col.default is not None and not callable(col.default.arg):
        val = col.default.arg
        if isinstance(val, bool):
            return f" DEFAULT {1 if val else 0}"
        if isinstance(val, (int, float)):
            return f" DEFAULT {val}"
        if isinstance(val, str):
            return f" DEFAULT '{val}'"
    return " DEFAULT NULL"


def _seed_defaults():
    """Populate missing SystemConfig keys with sensible defaults."""
    from .models import SystemConfig
    defaults = {
        "admin_username":  "admin",
        "admin_password":  _hash("admin"),   # change via Settings
        "smtp_host":       "",
        "smtp_port":       "587",
        "smtp_user":       "",
        "smtp_password":   "",
        "smtp_from":       "",
        "smtp_tls":        "1",
        "notify_email":    "",
        "base_url":        "http://localhost:5050",
        "timezone":        "America/Chicago",
    }
    for key, val in defaults.items():
        if not SystemConfig.query.get(key):
            db.session.add(SystemConfig(key=key, value=val))
    db.session.commit()


def _hash(password):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)
