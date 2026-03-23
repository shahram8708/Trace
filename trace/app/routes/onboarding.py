from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from ..extensions import db

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")

DOMAIN_OPTIONS = [
    {"name": "Product Management", "icon": "bi-diagram-3", "color": "domain-product"},
    {"name": "Software Engineering", "icon": "bi-cpu", "color": "domain-engineering"},
    {"name": "Data & Analytics", "icon": "bi-bar-chart-line", "color": "domain-data"},
    {"name": "Leadership & Management", "icon": "bi-people", "color": "domain-leadership"},
    {"name": "Marketing", "icon": "bi-bullseye", "color": "domain-marketing"},
    {"name": "Finance & Investing", "icon": "bi-cash-coin", "color": "domain-finance"},
    {"name": "Design & UX", "icon": "bi-palette", "color": "domain-design"},
    {"name": "Science & Research", "icon": "bi-beaker", "color": "domain-science"},
    {"name": "Psychology & Behavior", "icon": "bi-brain", "color": "domain-psychology"},
    {"name": "Business Strategy", "icon": "bi-briefcase", "color": "domain-strategy"},
    {"name": "Communication & Writing", "icon": "bi-chat-dots", "color": "domain-communication"},
    {"name": "General Knowledge", "icon": "bi-stars", "color": "domain-general"},
]

CONTENT_TYPES = [
    {"name": "Articles & Blogs", "icon": "bi-link-45deg", "description": "Web articles, newsletters, blog posts, industry publications"},
    {"name": "Books (Non-fiction)", "icon": "bi-book", "description": "Chapters, summaries, and book excerpts"},
    {"name": "Online Courses", "icon": "bi-laptop", "description": "Course notes, transcripts, and lesson takeaways"},
    {"name": "Podcasts", "icon": "bi-mic", "description": "Episode transcripts or notes"},
    {"name": "YouTube Videos", "icon": "bi-youtube", "description": "Video transcripts and key ideas"},
    {"name": "Academic Papers", "icon": "bi-file-earmark-text", "description": "Research papers and whitepapers"},
    {"name": "Conference Talks", "icon": "bi-easel", "description": "Talk notes and slide summaries"},
    {"name": "Newsletter Digests", "icon": "bi-envelope-open", "description": "Curated newsletters and digests"},
]

REVIEW_TIMES = [
    {"value": "06:00", "label": "6:00 AM"},
    {"value": "07:00", "label": "7:00 AM"},
    {"value": "08:00", "label": "8:00 AM"},
    {"value": "09:00", "label": "9:00 AM"},
    {"value": "10:00", "label": "10:00 AM"},
    {"value": "12:00", "label": "12:00 PM"},
    {"value": "13:00", "label": "1:00 PM"},
    {"value": "17:00", "label": "5:00 PM"},
    {"value": "18:00", "label": "6:00 PM"},
    {"value": "19:00", "label": "7:00 PM"},
    {"value": "20:00", "label": "8:00 PM"},
    {"value": "21:00", "label": "9:00 PM"},
]


def _default_domains():
    return ["General Knowledge"]


def _default_content_types():
    return ["Articles & Blogs"]


@onboarding_bp.route("/step1", methods=["GET", "POST"])
@login_required
def step1():
    if request.method == "POST":
        selected = request.form.getlist("domains")
        if not selected:
            flash("Select at least one domain to continue.", "warning")
            return render_template("onboarding/step1.html", domains=DOMAIN_OPTIONS)
        if len(selected) > 5:
            selected = selected[:5]
        session["onboarding_domains"] = selected
        return redirect(url_for("onboarding.step2"))
    return render_template("onboarding/step1.html", domains=DOMAIN_OPTIONS)


@onboarding_bp.route("/step2", methods=["GET", "POST"])
@login_required
def step2():
    if request.method == "POST":
        selected = request.form.getlist("content_types")
        session["onboarding_content_types"] = selected
        return redirect(url_for("onboarding.step3"))
    return render_template("onboarding/step2.html", content_types=CONTENT_TYPES)


@onboarding_bp.route("/step3", methods=["GET", "POST"])
@login_required
def step3():
    if request.method == "POST":
        review_time = request.form.get("review_time") or "08:00"
        domains = session.get("onboarding_domains") or _default_domains()
        content_types = session.get("onboarding_content_types") or _default_content_types()

        current_user.domains_of_interest = domains
        current_user.preferred_content_types = content_types
        current_user.review_reminder_time = review_time
        current_user.onboarding_complete = True
        db.session.commit()
        session.pop("onboarding_domains", None)
        session.pop("onboarding_content_types", None)
        flash(f"Welcome to Trace, {current_user.get_display_name()}! Let's build your first piece of knowledge.", "success")
        return redirect(url_for("import_bp.hub"))
    return render_template("onboarding/step3.html", review_times=REVIEW_TIMES)


@onboarding_bp.route("/skip")
@login_required
def skip():
    current_user.domains_of_interest = _default_domains()
    current_user.preferred_content_types = _default_content_types()
    current_user.review_reminder_time = "08:00"
    current_user.onboarding_complete = True
    db.session.commit()
    session.pop("onboarding_domains", None)
    session.pop("onboarding_content_types", None)
    return redirect(url_for("dashboard_bp.dashboard"))
