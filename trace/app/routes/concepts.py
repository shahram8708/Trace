from __future__ import annotations

from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from ..extensions import db
from ..models.concept import Concept
from ..models.review_event import ReviewEvent
from ..models.connection import ConceptConnection
from ..models.application_event import ApplicationEvent
from ..models.project import Project
from ..forms.concept_forms import ConceptEditForm
from ..services.sm2_engine import compute_retention_strength


concepts_bp = Blueprint("concepts_bp", __name__, url_prefix="/concepts")


@concepts_bp.route("")
@login_required
def library():
    search = request.args.get("search", "").strip()
    domain = request.args.get("domain", "").strip()
    sort = request.args.get("sort", "")
    page = request.args.get("page", 1, type=int)
    source_id = request.args.get("source_id", type=int)
    today = date.today()

    query = db.select(Concept).filter(Concept.user_id == current_user.id, Concept.is_active.is_(True))

    if search:
        like_term = f"%{search}%"
        query = query.filter(
            func.lower(Concept.name).like(func.lower(like_term)) | func.lower(Concept.description).like(func.lower(like_term))
        )
    if domain:
        query = query.filter(Concept.domain_tag == domain)
    if source_id:
        query = query.filter(Concept.source_item_id == source_id)

    if sort == "retention":
        query = query.order_by(Concept.retention_strength.asc())
    elif sort == "date":
        query = query.order_by(Concept.created_at.desc())
    elif sort == "name":
        query = query.order_by(Concept.name.asc())
    elif sort == "overdue":
        query = query.filter(Concept.next_review_due < today).order_by(Concept.next_review_due.asc())
    else:
        query = query.order_by(Concept.next_review_due.asc().nullslast())

    pagination = db.paginate(query, page=page, per_page=24, error_out=False)
    all_domains = (
        db.session.execute(
            db.select(Concept.domain_tag)
            .filter(Concept.user_id == current_user.id, Concept.is_active.is_(True), Concept.domain_tag.is_not(None))
            .distinct()
            .order_by(Concept.domain_tag.asc())
        )
        .scalars()
        .all()
    )

    return render_template(
        "concepts/library.html",
        concepts=pagination.items,
        pagination=pagination,
        search=search,
        domain=domain,
        sort=sort,
        all_domains=all_domains,
        total_count=pagination.total,
        today=today,
        source_id=source_id,
    )


@concepts_bp.route("/<int:concept_id>")
@login_required
def detail(concept_id: int):
    concept = db.session.get(Concept, concept_id)
    if not concept or concept.user_id != current_user.id:
        abort(404)

    history = (
        db.session.execute(
            db.select(ReviewEvent)
            .filter(ReviewEvent.concept_id == concept.id)
            .order_by(ReviewEvent.reviewed_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    retention_points = []
    for event in reversed(history):  # chronological for chart
        interval = event.new_interval or concept.sm2_interval or 1
        retention_points.append(
            {
                "date": event.reviewed_at.date().isoformat(),
                "retention_strength": compute_retention_strength(event.reviewed_at, interval),
            }
        )

    connections = (
        db.session.execute(
            db.select(ConceptConnection)
            .filter(
                (ConceptConnection.concept_a_id == concept.id) | (ConceptConnection.concept_b_id == concept.id),
                ConceptConnection.is_active.is_(True),
                ConceptConnection.user_id == current_user.id,
            )
        )
        .scalars()
        .all()
    )

    connected_concepts = []
    for conn in connections:
        other_id = conn.concept_b_id if conn.concept_a_id == concept.id else conn.concept_a_id
        other = db.session.get(Concept, other_id)
        if other:
            connected_concepts.append({"concept": other, "relationship_type": conn.relationship_type})

    suggested_connections = []
    if not connected_concepts:
        suggested_rows = (
            db.session.execute(
                db.select(Concept)
                .filter(
                    Concept.user_id == current_user.id,
                    Concept.is_active.is_(True),
                    Concept.id != concept.id,
                    Concept.domain_tag == concept.domain_tag,
                )
                .order_by(Concept.last_reviewed.desc().nullslast())
                .limit(5)
            )
            .scalars()
            .all()
        )
        for other in suggested_rows:
            suggested_connections.append({"concept": other, "relationship_type": "Same domain"})

    application_events = (
        db.session.execute(
            db.select(ApplicationEvent)
            .filter(ApplicationEvent.concept_id == concept.id)
            .order_by(ApplicationEvent.prompted_at.desc())
            .limit(3)
        )
        .scalars()
        .all()
    )

    suggested_application_prompts = []
    if not application_events:
        projects = (
            db.session.execute(
                db.select(Project).filter(Project.user_id == current_user.id, Project.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        for project in projects:
            tags = project.domain_tags or []
            if concept.domain_tag and tags and concept.domain_tag not in tags:
                continue
            prompt_text = (
                f"How can you apply '{concept.name}' to your project '{project.name}' this week? "
                "Outline one concrete action or deliverable."
            )
            suggested_application_prompts.append({
                "project_name": project.name,
                "prompt_text": prompt_text,
            })
            if len(suggested_application_prompts) >= 3:
                break

        if not suggested_application_prompts:
            # Fallback prompts when there are no projects or domain tags don't match
            generic_prompts = [
                {
                    "project_name": "Personal practice",
                    "prompt_text": f"Draft a 3-sentence scenario where you use '{concept.name}' today. What exact steps would you take?",
                },
                {
                    "project_name": "Work task",
                    "prompt_text": f"Identify one upcoming task where '{concept.name}' applies. Write the task and the first action you'll do in 10 minutes.",
                },
            ]
            suggested_application_prompts.extend(generic_prompts)

    return render_template(
        "concepts/detail.html",
        concept=concept,
        history=history,
        retention_points=retention_points,
        connected_concepts=connected_concepts,
        suggested_connections=suggested_connections,
        application_events=application_events,
        suggested_application_prompts=suggested_application_prompts,
    )


@concepts_bp.route("/<int:concept_id>/edit", methods=["GET", "POST"])
@login_required
def edit(concept_id: int):
    concept = db.session.get(Concept, concept_id)
    if not concept or concept.user_id != current_user.id:
        abort(404)

    form = ConceptEditForm(obj=concept)
    if form.validate_on_submit():
        concept.name = form.name.data
        concept.description = form.description.data
        concept.domain_tag = form.domain_tag.data
        concept.source_excerpt = form.source_excerpt.data
        db.session.commit()
        flash("Concept updated.", "success")
        return redirect(url_for("concepts_bp.detail", concept_id=concept.id))

    return render_template("concepts/edit.html", form=form, concept=concept)


@concepts_bp.route("/<int:concept_id>/deactivate", methods=["POST"])
@login_required
def deactivate(concept_id: int):
    concept = db.session.get(Concept, concept_id)
    if not concept or concept.user_id != current_user.id:
        abort(404)
    concept.is_active = False
    db.session.commit()
    flash("Concept removed from your review queue. You can reactivate it from your concept library.", "info")
    return redirect(url_for("concepts_bp.library"))


@concepts_bp.route("/<int:concept_id>/reactivate", methods=["POST"])
@login_required
def reactivate(concept_id: int):
    concept = db.session.get(Concept, concept_id)
    if not concept or concept.user_id != current_user.id:
        abort(404)
    concept.is_active = True
    if concept.next_review_due is None or concept.next_review_due < date.today():
        concept.next_review_due = date.today() + timedelta(days=1)
    db.session.commit()
    flash("Concept added back to your review queue.", "success")
    return redirect(url_for("concepts_bp.detail", concept_id=concept.id))


@concepts_bp.route("/domain/<string:domain>")
@login_required
def by_domain(domain: str):
    return redirect(url_for("concepts_bp.library", domain=domain))
