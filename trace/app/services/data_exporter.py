import csv
import io
from datetime import datetime
from typing import Dict

from ..models.concept import Concept
from ..models.source_item import SourceItem
from ..models.review_event import ReviewEvent
from ..models.connection import ConceptConnection
from ..models.project import Project
from ..extensions import db


def _write_csv(rows, headers):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def export_user_data_as_csv(user) -> Dict[str, str]:
    user_id = user.id

    concepts = (
        db.session.query(Concept)
        .filter(Concept.user_id == user_id)
        .order_by(Concept.id.asc())
        .all()
    )
    concept_rows = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "domain_tag": c.domain_tag,
            "source_excerpt": c.source_excerpt,
            "created_at": c.created_at,
            "last_reviewed": c.last_reviewed,
            "next_review_due": c.next_review_due,
            "sm2_ease_factor": c.sm2_ease_factor,
            "sm2_interval": c.sm2_interval,
            "sm2_repetitions": c.sm2_repetitions,
            "retention_strength": c.retention_strength,
            "total_reviews": c.total_reviews,
            "is_active": c.is_active,
            "is_mature": c.is_mature,
        }
        for c in concepts
    ]
    concepts_csv = _write_csv(concept_rows, list(concept_rows[0].keys()) if concept_rows else [])

    sources = (
        db.session.query(SourceItem)
        .filter(SourceItem.user_id == user_id)
        .order_by(SourceItem.id.asc())
        .all()
    )
    source_rows = [
        {
            "id": s.id,
            "title": s.title,
            "source_url": s.source_url,
            "source_type": s.source_type,
            "import_date": s.import_date,
            "domain_tags": s.domain_tags,
            "word_count": s.word_count,
            "author": s.author,
            "concept_count": s.concept_count,
        }
        for s in sources
    ]
    sources_csv = _write_csv(source_rows, list(source_rows[0].keys()) if source_rows else [])

    reviews = (
        db.session.query(ReviewEvent)
        .filter(ReviewEvent.user_id == user_id)
        .order_by(ReviewEvent.id.asc())
        .all()
    )
    review_rows = [
        {
            "id": r.id,
            "concept_id": r.concept_id,
            "concept_name": r.concept.name if r.concept else None,
            "reviewed_at": r.reviewed_at,
            "quality_rating": r.quality_rating,
            "previous_interval": r.previous_interval,
            "new_interval": r.new_interval,
            "session_id": r.session_id,
        }
        for r in reviews
    ]
    reviews_csv = _write_csv(review_rows, list(review_rows[0].keys()) if review_rows else [])

    connections = (
        db.session.query(ConceptConnection)
        .filter(ConceptConnection.user_id == user_id)
        .order_by(ConceptConnection.id.asc())
        .all()
    )
    connection_rows = [
        {
            "id": c.id,
            "concept_a_name": c.concept_a.name if c.concept_a else None,
            "concept_b_name": c.concept_b.name if c.concept_b else None,
            "relationship_type": c.relationship_type,
            "connection_source": c.connection_source,
            "created_at": c.created_at,
        }
        for c in connections
    ]
    connections_csv = _write_csv(connection_rows, list(connection_rows[0].keys()) if connection_rows else [])

    projects = (
        db.session.query(Project)
        .filter(Project.user_id == user_id)
        .order_by(Project.id.asc())
        .all()
    )
    project_rows = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "domain_tags": p.domain_tags,
            "is_active": p.is_active,
            "created_at": p.created_at,
            "reminder_frequency": p.reminder_frequency,
        }
        for p in projects
    ]
    projects_csv = _write_csv(project_rows, list(project_rows[0].keys()) if project_rows else [])

    return {
        "concepts.csv": concepts_csv,
        "sources.csv": sources_csv,
        "review_history.csv": reviews_csv,
        "connections.csv": connections_csv,
        "projects.csv": projects_csv,
    }
