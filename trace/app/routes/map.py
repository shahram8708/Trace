import json

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models.concept import Concept
from ..models.connection import ConceptConnection
from ..services.connection_suggester import (
    compute_and_store_suggestions,
    get_pending_suggestions,
    accept_suggestion,
    dismiss_suggestion,
)
from ..utils.decorators import premium_required

map_bp = Blueprint("map_bp", __name__, url_prefix="/map")

RELATIONSHIP_TYPES = {"builds on", "contradicts", "applies to", "example of", "related to"}


@map_bp.route("", methods=["GET"])
@login_required
@premium_required
def map_view():
    concepts = Concept.query.filter_by(user_id=current_user.id, is_active=True).all()
    connections = ConceptConnection.query.filter_by(user_id=current_user.id, is_active=True).all()

    total_concept_count = len(concepts)
    graph_truncated = False
    if total_concept_count > 500:
        concepts = sorted(concepts, key=lambda c: c.total_reviews or 0, reverse=True)[:500]
        graph_truncated = True

    concept_lookup = {c.id: c for c in concepts}

    nodes = []
    for concept in concepts:
        nodes.append(
            {
                "id": concept.id,
                "label": concept.name,
                "domain": concept.domain_tag,
                "retention": concept.retention_strength,
                "is_mature": concept.is_mature,
                "source_title": concept.source_item.title if concept.source_item else "Manual",
                "reviews": concept.total_reviews,
                "description": concept.description,
            }
        )

    edges = []
    for conn in connections:
        if conn.concept_a_id not in concept_lookup or conn.concept_b_id not in concept_lookup:
            continue
        edges.append(
            {
                "id": conn.id,
                "source": conn.concept_a_id,
                "target": conn.concept_b_id,
                "relationship": conn.relationship_type,
                "connection_source": conn.connection_source,
            }
        )

    suggestions = get_pending_suggestions(current_user.id)
    if not suggestions:
        # Fallback for setups where the Celery job hasn't populated suggestions yet.
        compute_and_store_suggestions(current_user.id)
        suggestions = get_pending_suggestions(current_user.id)
    domain_list = sorted({c.domain_tag for c in concepts if c.domain_tag})

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)
    suggestions_json = json.dumps(
        [
            {
                "concept_a_id": s["concept_a_id"],
                "concept_b_id": s["concept_b_id"],
                "concept_a_name": s["concept_a"].name,
                "concept_b_name": s["concept_b"].name,
                "score": s.get("score"),
                "suggested_relationship": s.get("suggested_relationship", "related to"),
            }
            for s in suggestions
        ]
    )

    return render_template(
        "map/knowledge_map.html",
        nodes_json=nodes_json,
        edges_json=edges_json,
        suggestions_json=suggestions_json,
        domain_list=domain_list,
        graph_truncated=graph_truncated,
        total_concept_count=total_concept_count,
    )


@map_bp.route("/connect", methods=["POST"])
@login_required
@premium_required
def connect():
    payload = request.get_json() or {}
    concept_a_id = int(payload.get("concept_a_id", 0))
    concept_b_id = int(payload.get("concept_b_id", 0))
    relationship_type = payload.get("relationship_type", "").strip()

    if relationship_type not in RELATIONSHIP_TYPES:
        return jsonify({"success": False, "error": "Invalid relationship"}), 400

    concepts = Concept.query.filter(
        Concept.user_id == current_user.id,
        Concept.id.in_([concept_a_id, concept_b_id]),
    ).all()
    if len(concepts) != 2:
        return jsonify({"success": False, "error": "Concepts not found"}), 404

    existing = ConceptConnection.query.filter_by(
        user_id=current_user.id,
        concept_a_id=min(concept_a_id, concept_b_id),
        concept_b_id=max(concept_a_id, concept_b_id),
    ).first()
    if existing:
        return jsonify({"success": False, "error": "Connection already exists"}), 400

    connection = ConceptConnection(
        user_id=current_user.id,
        concept_a_id=min(concept_a_id, concept_b_id),
        concept_b_id=max(concept_a_id, concept_b_id),
        relationship_type=relationship_type,
        connection_source="user",
        is_active=True,
    )
    db.session.add(connection)
    db.session.commit()
    return jsonify({"success": True, "connection_id": connection.id, "message": "Connection saved."})


@map_bp.route("/connect/<int:conn_id>/delete", methods=["POST"])
@login_required
@premium_required
def delete_connection(conn_id: int):
    connection = ConceptConnection.query.filter_by(id=conn_id, user_id=current_user.id).first_or_404()
    connection.is_active = False
    db.session.commit()
    return jsonify({"success": True})


@map_bp.route("/suggestions", methods=["GET"])
@login_required
@premium_required
def suggestions():
    suggestions = get_pending_suggestions(current_user.id)
    if not suggestions:
        compute_and_store_suggestions(current_user.id)
        suggestions = get_pending_suggestions(current_user.id)

    data = []
    for s in suggestions:
        data.append(
            {
                "concept_a_id": s["concept_a_id"],
                "concept_b_id": s["concept_b_id"],
                "concept_a_name": s["concept_a"].name,
                "concept_b_name": s["concept_b"].name,
                "score": s.get("score"),
                "suggested_relationship": s.get("suggested_relationship", "related to"),
            }
        )
    return jsonify(data)


@map_bp.route("/suggestions/accept", methods=["POST"])
@login_required
@premium_required
def accept():
    payload = request.get_json() or {}
    concept_a_id = int(payload.get("concept_a_id", 0))
    concept_b_id = int(payload.get("concept_b_id", 0))
    relationship_type = payload.get("relationship_type", "related to")
    if relationship_type not in RELATIONSHIP_TYPES:
        return jsonify({"success": False, "error": "Invalid relationship"}), 400
    try:
        connection = accept_suggestion(current_user.id, concept_a_id, concept_b_id, relationship_type)
        return jsonify({"success": True, "connection_id": connection.id})
    except Exception:
        return jsonify({"success": False, "error": "Unable to accept suggestion"}), 400


@map_bp.route("/suggestions/dismiss", methods=["POST"])
@login_required
@premium_required
def dismiss():
    payload = request.get_json() or {}
    concept_a_id = int(payload.get("concept_a_id", 0))
    concept_b_id = int(payload.get("concept_b_id", 0))
    dismiss_suggestion(current_user.id, concept_a_id, concept_b_id)
    return jsonify({"success": True})
