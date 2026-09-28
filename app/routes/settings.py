from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from werkzeug.security import generate_password_hash

from .. import db
from ..models import SystemConfig

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        # SMTP settings
        for key in ("smtp_host", "smtp_port", "smtp_user", "smtp_from",
                    "notify_email", "base_url", "timezone", "history_limit"):
            SystemConfig.set(key, request.form.get(key, "").strip())
        SystemConfig.set("smtp_tls", "1" if request.form.get("smtp_tls") else "0")
        smtp_pass = request.form.get("smtp_password", "")
        if smtp_pass:
            SystemConfig.set("smtp_password", smtp_pass)

        # Admin credentials
        new_user = request.form.get("admin_username", "").strip()
        new_pass = request.form.get("new_password", "")
        confirm  = request.form.get("confirm_password", "")
        if new_user:
            SystemConfig.set("admin_username", new_user)
        if new_pass:
            if new_pass != confirm:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("settings.settings"))
            SystemConfig.set("admin_password", generate_password_hash(new_pass))

        flash("Settings saved.", "success")
        return redirect(url_for("settings.settings"))

    cfg = {
        "smtp_host":    SystemConfig.get("smtp_host"),
        "smtp_port":    SystemConfig.get("smtp_port", "587"),
        "smtp_user":    SystemConfig.get("smtp_user"),
        "smtp_from":    SystemConfig.get("smtp_from"),
        "smtp_tls":     SystemConfig.get("smtp_tls", "1") == "1",
        "notify_email": SystemConfig.get("notify_email"),
        "base_url":     SystemConfig.get("base_url"),
        "admin_username": SystemConfig.get("admin_username", "admin"),
        "timezone":       SystemConfig.get("timezone", "America/Chicago"),
        "history_limit":  SystemConfig.get("history_limit", "500"),
    }
    return render_template("settings.html", cfg=cfg)
