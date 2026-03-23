from __future__ import annotations

from datetime import date
from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from ..extensions import db
from ..models.source_item import SourceItem
from ..models.concept import Concept


library_bp = Blueprint("library_bp", __name__, url_prefix="/library")


@library_bp.route("")
@login_required
def index():
    search = request.args.get("search", "").strip()
    source_type = request.args.get("source_type", "").strip().lower()
    sort = request.args.get("sort", "date")
    page = request.args.get("page", 1, type=int)

    query = db.select(SourceItem).filter(SourceItem.user_id == current_user.id)

    if search:
        like_term = f"%{search}%"
        query = query.filter(func.lower(SourceItem.title).like(func.lower(like_term)))
    if source_type:
        query = query.filter(SourceItem.source_type == source_type)

    if sort == "concepts":
        query = query.order_by(SourceItem.concept_count.desc())
    elif sort == "title":
        query = query.order_by(SourceItem.title.asc())
    else:
        query = query.order_by(SourceItem.import_date.desc())

    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    sources = pagination.items

    # Compute retention health per source
    retention_map = {}
    if sources:
        for src in sources:
            avg_retention = db.session.execute(
                db.select(func.avg(Concept.retention_strength)).filter(
                    Concept.source_item_id == src.id, Concept.is_active.is_(True)
                )
            ).scalar_one_or_none()
            retention_map[src.id] = float(avg_retention or 0.0)

    counts_rows = db.session.execute(
        db.session.query(SourceItem.source_type, func.count(SourceItem.id))
        .filter(SourceItem.user_id == current_user.id)
        .group_by(SourceItem.source_type)
    ).all()
    source_type_counts = {row[0]: row[1] for row in counts_rows}

    return render_template(
        "library/index.html",
        sources=sources,
        pagination=pagination,
        search=search,
        source_type=source_type,
        sort=sort,
        source_type_counts=source_type_counts,
        retention_map=retention_map,
    )


@library_bp.route("/<int:source_id>")
@login_required
def detail(source_id: int):
    source_item = db.session.get(SourceItem, source_id)
    if not source_item or source_item.user_id != current_user.id:
        abort(404)

    concepts = (
        db.session.execute(
            db.select(Concept).filter(Concept.source_item_id == source_item.id).order_by(Concept.name.asc())
        )
        .scalars()
        .all()
    )

    avg_retention = db.session.execute(
        db.select(func.avg(Concept.retention_strength)).filter(
            Concept.source_item_id == source_item.id, Concept.is_active.is_(True)
        )
    ).scalar_one_or_none()
    avg_retention = float(avg_retention or 0.0)
    mature_count = db.session.execute(
        db.select(func.count(Concept.id)).filter(
            Concept.source_item_id == source_item.id, Concept.is_active.is_(True), Concept.is_mature.is_(True)
        )
    ).scalar_one()
    active_count = db.session.execute(
        db.select(func.count(Concept.id)).filter(
            Concept.source_item_id == source_item.id, Concept.is_active.is_(True)
        )
    ).scalar_one()

    today = date.today()
    overdue_count = db.session.execute(
        db.select(func.count(Concept.id)).filter(
            Concept.source_item_id == source_item.id,
            Concept.is_active.is_(True),
            Concept.next_review_due.is_not(None),
            Concept.next_review_due < today,
        )
    ).scalar_one()
    reviewed_count = db.session.execute(
        db.select(func.count(Concept.id)).filter(
            Concept.source_item_id == source_item.id,
            Concept.total_reviews > 0,
        )
    ).scalar_one()

    return render_template(
        "library/detail.html",
        source=source_item,
        concepts=concepts,
        avg_retention=avg_retention,
        mature_count=mature_count,
        active_count=active_count,
        overdue_count=overdue_count,
        reviewed_count=reviewed_count,
    )
