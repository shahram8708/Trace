import re
from datetime import datetime
from itertools import combinations
from typing import List, Dict, Tuple

from sqlalchemy import or_

from ..extensions import db
from ..models.user import User
from ..models.concept import Concept
from ..models.connection import ConceptConnection


def _tokenize_text(*texts: str) -> set:
    tokens = set()
    for text in texts:
        if not text:
            continue
        tokens.update(re.findall(r"[A-Za-z0-9]+", text.lower()))
    return tokens


def _pair_key(a_id: int, b_id: int) -> Tuple[int, int]:
    return tuple(sorted((int(a_id), int(b_id))))


def compute_and_store_suggestions(user_id: int) -> List[Dict[str, object]]:
    user = db.session.get(User, user_id)
    if not user:
        return []

    concepts: List[Concept] = (
        db.session.query(Concept)
        .filter(Concept.user_id == user_id, Concept.is_active.is_(True))
        .all()
    )
    if len(concepts) < 2:
        return []

    active_concept_ids = {c.id for c in concepts}

    existing_connections = {
        _pair_key(conn.concept_a_id, conn.concept_b_id)
        for conn in db.session.query(ConceptConnection).filter_by(user_id=user_id).all()
    }

    existing_suggestions = user.suggested_connections or []
    dismissed_pairs = {
        _pair_key(item.get("concept_a_id"), item.get("concept_b_id"))
        for item in existing_suggestions
        if item.get("dismissed")
    }

    suggestion_map: Dict[Tuple[int, int], Dict[str, object]] = {}

    for concept_a, concept_b in combinations(concepts, 2):
        key = _pair_key(concept_a.id, concept_b.id)
        if key in existing_connections or key in dismissed_pairs:
            continue

        score = 0.0
        same_domain = concept_a.domain_tag and concept_a.domain_tag == concept_b.domain_tag
        same_source = concept_a.source_item_id and concept_a.source_item_id == concept_b.source_item_id
        if same_domain:
            score += 0.4
        if same_source:
            score += 0.3

        tokens_a = _tokenize_text(concept_a.name, concept_a.description)
        tokens_b = _tokenize_text(concept_b.name, concept_b.description)
        union = tokens_a | tokens_b
        if union:
            jaccard = len(tokens_a & tokens_b) / len(union)
            score += jaccard * 0.3

        if score < 0.5:
            continue

        suggested_relationship = "builds on" if same_source else "related to"
        suggestion_map[key] = {
            "concept_a_id": concept_a.id,
            "concept_b_id": concept_b.id,
            "score": round(score, 3),
            "suggested_at": datetime.utcnow().isoformat(),
            "dismissed": False,
            "suggested_relationship": suggested_relationship,
        }

    # Merge with existing suggestions that are still valid
    for item in existing_suggestions:
        key = _pair_key(item.get("concept_a_id"), item.get("concept_b_id"))
        if key in existing_connections:
            continue
        if not all(cid in active_concept_ids for cid in key):
            continue
        if key not in suggestion_map:
            suggestion_map[key] = item
        else:
            # Preserve dismissal state if it existed
            suggestion_map[key]["dismissed"] = suggestion_map[key].get("dismissed") or item.get("dismissed", False)

    sorted_suggestions = sorted(suggestion_map.values(), key=lambda s: s.get("score", 0), reverse=True)[:30]
    user.suggested_connections = sorted_suggestions
    db.session.commit()
    return sorted_suggestions


def get_pending_suggestions(user_id: int, limit: int = 20) -> List[Dict[str, object]]:
    user = db.session.get(User, user_id)
    if not user:
        return []
    suggestions = user.suggested_connections or []
    concept_ids = set()
    for item in suggestions:
        if item.get("dismissed"):
            continue
        concept_ids.update([item.get("concept_a_id"), item.get("concept_b_id")])
    concepts = {
        c.id: c
        for c in db.session.query(Concept)
        .filter(Concept.user_id == user_id, Concept.id.in_(concept_ids), Concept.is_active.is_(True))
        .all()
    }

    pending: List[Dict[str, object]] = []
    for item in suggestions:
        if item.get("dismissed"):
            continue
        key = _pair_key(item.get("concept_a_id"), item.get("concept_b_id"))
        if not all(cid in concepts for cid in key):
            continue
        entry = dict(item)
        entry["concept_a"] = concepts[key[0]]
        entry["concept_b"] = concepts[key[1]]
        pending.append(entry)

    pending.sort(key=lambda s: s.get("score", 0), reverse=True)
    return pending[:limit]


def dismiss_suggestion(user_id: int, concept_a_id: int, concept_b_id: int) -> bool:
    user = db.session.get(User, user_id)
    if not user:
        return False
    key = _pair_key(concept_a_id, concept_b_id)
    updated = False
    suggestions = user.suggested_connections or []
    for item in suggestions:
        if _pair_key(item.get("concept_a_id"), item.get("concept_b_id")) == key:
            item["dismissed"] = True
            updated = True
    if updated:
        user.suggested_connections = suggestions
        db.session.commit()
    return updated


def accept_suggestion(user_id: int, concept_a_id: int, concept_b_id: int, relationship_type: str) -> ConceptConnection:
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    concepts = db.session.query(Concept).filter(
        Concept.user_id == user_id,
        Concept.id.in_([concept_a_id, concept_b_id]),
    ).all()
    if len(concepts) != 2:
        raise ValueError("Concepts not found or not owned by user")

    key = _pair_key(concept_a_id, concept_b_id)
    existing = db.session.query(ConceptConnection).filter_by(
        user_id=user_id,
        concept_a_id=key[0],
        concept_b_id=key[1],
    ).first()
    if existing:
        return existing

    connection = ConceptConnection(
        user_id=user_id,
        concept_a_id=key[0],
        concept_b_id=key[1],
        relationship_type=relationship_type,
        connection_source="user",
        is_active=True,
    )
    db.session.add(connection)

    remaining = []
    for item in user.suggested_connections or []:
        if _pair_key(item.get("concept_a_id"), item.get("concept_b_id")) == key:
            continue
        remaining.append(item)
    user.suggested_connections = remaining
    db.session.commit()
    return connection
