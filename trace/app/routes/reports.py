from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from ..utils.decorators import premium_required
from ..services.report_generator import generate_weekly_report_data

reports_bp = Blueprint("reports_bp", __name__, url_prefix="/reports")


@reports_bp.route("", methods=["GET"])
@login_required
@premium_required
def index():
    report_data = generate_weekly_report_data(current_user.id)
    return render_template("reports/index.html", report_data=report_data)


@reports_bp.route("/generate", methods=["GET"])
@login_required
@premium_required
def regenerate():
    generate_weekly_report_data(current_user.id)
    return redirect(url_for("reports_bp.index"))
