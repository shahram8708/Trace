from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..forms.project_forms import ProjectForm
from ..models.project import Project
from ..models.concept import Concept
from ..models.application_event import ApplicationEvent
from ..tasks import send_application_reminders_for_user
from ..utils.decorators import premium_required

projects_bp = Blueprint("projects_bp", __name__, url_prefix="/projects")


@projects_bp.route("", methods=["GET"])
@login_required
@premium_required
def index():
    projects = (
        Project.query.filter_by(user_id=current_user.id)
        .order_by(Project.is_active.desc(), Project.created_at.desc())
        .all()
    )
    matched_counts = {}
    for project in projects:
        query = db.select(func.count(Concept.id)).filter(
            Concept.user_id == current_user.id,
            Concept.is_active.is_(True),
        )
        if project.domain_tags:
            query = query.filter(Concept.domain_tag.in_(project.domain_tags))
        count = db.session.scalar(query) or 0
        matched_counts[project.id] = int(count)
    return render_template("projects/index.html", projects=projects, matched_counts=matched_counts)


@projects_bp.route("/new", methods=["GET", "POST"])
@login_required
@premium_required
def new():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            user_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            domain_tags=form.domain_tags.data,
            reminder_frequency=form.reminder_frequency.data,
            is_active=form.is_active.data,
        )
        db.session.add(project)
        db.session.commit()
        try:
            send_application_reminders_for_user.delay(current_user.id)
        except Exception:  # pragma: no cover
            pass
        flash("Project created. We'll match relevant concepts from your library.", "success")
        return redirect(url_for("projects_bp.detail", project_id=project.id))
    return render_template("projects/new.html", form=form)


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
@premium_required
def detail(project_id: int):
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    form = ProjectForm(obj=project)
    concept_query = Concept.query.filter(
        Concept.user_id == current_user.id,
        Concept.is_active.is_(True),
    )
    if project.domain_tags:
        concept_query = concept_query.filter(Concept.domain_tag.in_(project.domain_tags))
    matched_concepts = concept_query.order_by(Concept.retention_strength.asc()).limit(20).all()
    pending_prompts = (
        ApplicationEvent.query.filter_by(project_id=project.id, user_id=current_user.id, user_response=None)
        .order_by(ApplicationEvent.prompted_at.desc())
        .limit(5)
        .all()
    )
    history = (
        ApplicationEvent.query.filter_by(project_id=project.id, user_id=current_user.id)
        .order_by(ApplicationEvent.prompted_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "projects/detail.html",
        project=project,
        matched_concepts=matched_concepts,
        pending_prompts=pending_prompts,
        history=history,
        form=form,
    )


@projects_bp.route("/<int:project_id>/edit", methods=["POST"])
@login_required
@premium_required
def edit(project_id: int):
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    form = ProjectForm()
    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data
        project.domain_tags = form.domain_tags.data
        project.reminder_frequency = form.reminder_frequency.data
        project.is_active = form.is_active.data
        db.session.commit()
        flash("Project updated.", "success")
    else:
        flash("Unable to update project.", "danger")
    return redirect(url_for("projects_bp.detail", project_id=project.id))


@projects_bp.route("/<int:project_id>/delete", methods=["POST"])
@login_required
@premium_required
def delete(project_id: int):
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    db.session.query(ApplicationEvent).filter_by(project_id=project.id).delete()
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "info")
    return redirect(url_for("projects_bp.index"))


@projects_bp.route("/<int:project_id>/respond", methods=["POST"])
@login_required
@premium_required
def respond(project_id: int):
    event_id = int(request.form.get("application_event_id", 0))
    response_value = request.form.get("response")
    if response_value not in {"applied", "not_relevant", "saved_for_later"}:
        return jsonify({"success": False, "error": "Invalid response"}), 400
    event = ApplicationEvent.query.filter_by(id=event_id, project_id=project_id, user_id=current_user.id).first_or_404()
    event.user_response = response_value
    event.responded_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})


@projects_bp.route("/preview-matches", methods=["GET"])
@login_required
@premium_required
def preview_matches():
    domains_param = request.args.get("domains", "")
    domains = [d for d in domains_param.split(",") if d]
    concepts_query = Concept.query.filter(
        Concept.user_id == current_user.id,
        Concept.is_active.is_(True),
    )
    if domains:
        concepts_query = concepts_query.filter(Concept.domain_tag.in_(domains))
    concepts_query = concepts_query.order_by(Concept.retention_strength.asc())
    count = concepts_query.count()
    samples = [c.name for c in concepts_query.limit(5).all()]
    return jsonify({"count": count, "samples": samples})
