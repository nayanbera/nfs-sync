from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

from ..models import AdminUser, SystemConfig

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        stored_user = SystemConfig.get("admin_username", "admin")
        stored_hash = SystemConfig.get("admin_password", "")
        if username == stored_user and check_password_hash(stored_hash, password):
            login_user(AdminUser())
            return redirect(url_for("jobs.list_jobs"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
