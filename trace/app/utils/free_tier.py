import os
from datetime import datetime, timedelta
from typing import Dict, Any
from ..extensions import db
from ..models.concept import Concept
from ..models.source_item import SourceItem
from ..models.ai_extraction_queue import AIExtractionQueue


def _get_limit_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def check_free_tier_limits(user) -> Dict[str, Any]:
    """Return free tier usage metrics for a user."""
    if not user:
        return {
            "concept_limit_reached": False,
            "concepts_remaining": 0,
            "import_limit_reached": False,
            "imports_remaining": 0,
            "extraction_limit_reached": False,
            "extractions_remaining": 0,
            "should_warn": False,
            "ok": False,
        }

    # Premium users bypass limits entirely
    if getattr(user, "is_premium", False):
        return {
            "concept_limit_reached": False,
            "concepts_remaining": None,
            "import_limit_reached": False,
            "imports_remaining": None,
            "extraction_limit_reached": False,
            "extractions_remaining": None,
            "should_warn": False,
            "ok": True,
        }

    concept_limit = _get_limit_env("FREE_CONCEPT_LIMIT", 50)
    extraction_limit = _get_limit_env("DAILY_AI_EXTRACTIONS_FREE", 5)
    import_limit = 5

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    active_concepts = (
        db.session.query(Concept)
        .filter(Concept.user_id == user.id, Concept.is_active.is_(True))
        .count()
    )
    recent_imports = (
        db.session.query(SourceItem)
        .filter(SourceItem.user_id == user.id, SourceItem.import_date >= thirty_days_ago)
        .count()
    )
    recent_extractions = (
        db.session.query(AIExtractionQueue)
        .join(SourceItem, AIExtractionQueue.source_item_id == SourceItem.id)
        .filter(SourceItem.user_id == user.id, AIExtractionQueue.created_at >= thirty_days_ago)
        .count()
    )

    concepts_remaining = max(concept_limit - active_concepts, 0)
    imports_remaining = max(import_limit - recent_imports, 0)
    extractions_remaining = max(extraction_limit - recent_extractions, 0)

    concept_limit_reached = active_concepts >= concept_limit
    import_limit_reached = recent_imports >= import_limit
    extraction_limit_reached = recent_extractions >= extraction_limit

    should_warn = not concept_limit_reached and concepts_remaining <= 5
    ok = not (concept_limit_reached or import_limit_reached or extraction_limit_reached)

    return {
        "concept_limit_reached": concept_limit_reached,
        "concepts_remaining": concepts_remaining,
        "import_limit_reached": import_limit_reached,
        "imports_remaining": imports_remaining,
        "extraction_limit_reached": extraction_limit_reached,
        "extractions_remaining": extractions_remaining,
        "should_warn": should_warn,
        "ok": ok,
    }


def get_upgrade_message(limit_type: str) -> str:
    messages = {
        "concepts": "You have reached the free tier concept limit. Upgrade to Pro for unlimited concepts and faster reviews.",
        "imports": "You have used all free imports for this month. Upgrade to Pro to import without limits.",
        "extractions": "You've hit the AI extraction limit. Upgrade to Pro for unlimited AI concept extraction.",
    }
    return messages.get(limit_type, "Upgrade to Trace Pro to remove free tier limits and unlock advanced features.")
