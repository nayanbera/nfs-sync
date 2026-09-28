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
        _seed_defaults()
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

    return app


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
    }
    for key, val in defaults.items():
        if not SystemConfig.query.get(key):
            db.session.add(SystemConfig(key=key, value=val))
    db.session.commit()


def _hash(password):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)
