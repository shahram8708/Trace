import json
import logging
import traceback
from datetime import datetime
from typing import List
from sqlalchemy import asc

from ..extensions import db
from ..models.project import Project
from ..models.concept import Concept
from ..models.application_event import ApplicationEvent
from ..utils.gemini_parser import call_gemini_with_search_and_retry

logger = logging.getLogger(__name__)


def generate_single_application_prompt(concept: Concept, project: Project) -> str:
    function_label = "generate_single_application_prompt"
    fallback = (
        f"You're working on '{project.name}'. How could the concept of '{concept.name}' apply to your current work? "
        "Take 2 minutes to write down one specific way you could use this."
    )
    print(
        f"\n[{function_label}] STARTED | Params: concept_id={getattr(concept, 'id', 'n/a')} | project_id={getattr(project, 'id', 'n/a')}"
    )

    try:
        prompt = (
            "Generate a short, specific application prompt that helps the user apply the concept "
            f"'{concept.name}' to the project '{project.name}'. "
            f"Project description: {project.description or 'No description provided.'} "
            f"Concept description: {concept.description[:400]} "
            "Ask a concrete question in 2-3 sentences that encourages practical action."
        )

        response_text = call_gemini_with_search_and_retry(
            prompt,
            context_label="application_prompt",
        )
        print(f"[APPLICATION PROMPT] Raw AI response: {response_text}")

        if response_text is None:
            print(f"[{function_label}] COMPLETED WITH FALLBACK | Reason: response is None")
            return fallback

        cleaned = response_text.strip()
        if len(cleaned) < 30:
            print(f"[{function_label}] WARNING | Response too short ({len(cleaned)} chars). Returning fallback.")
            return fallback

        print(f"[{function_label}] COMPLETED SUCCESSFULLY | Result length: {len(cleaned)}")
        return cleaned

    except json.JSONDecodeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] JSON DECODE ERROR")
        print(f"[{function_label}] Error message: {str(e)}")
        print(f"[{function_label}] Error position: line {e.lineno}, column {e.colno}, char {e.pos}")
        print(
            f"[{function_label}] Document snippet around error: {e.doc[max(0,e.pos-50):e.pos+50] if e.doc else 'N/A'}"
        )
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] JSONDecodeError: {e}", exc_info=True)
        return fallback

    except AttributeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] ATTRIBUTE ERROR (likely response.text is None or response object is unexpected)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] AttributeError: {e}", exc_info=True)
        return fallback

    except TypeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] TYPE ERROR (likely json.loads received wrong type)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] TypeError: {e}", exc_info=True)
        return fallback

    except Exception as e:  # pragma: no cover
        print(f"\n{'!'*60}")
        print(f"[{function_label}] UNEXPECTED ERROR")
        print(f"[{function_label}] Error type: {type(e).__name__}")
        print(f"[{function_label}] Error message: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] Unexpected error: {e}", exc_info=True)
        return fallback


def generate_application_reminders(user_id: int, project_id: int) -> List[ApplicationEvent]:
    project = db.session.get(Project, project_id)
    if not project or project.user_id != user_id:
        return []

    query = db.select(Concept).filter(
        Concept.user_id == user_id,
        Concept.is_active.is_(True),
    )
    if project.domain_tags:
        query = query.filter(Concept.domain_tag.in_(project.domain_tags))
    # SQLite does not support "NULLS LAST"; sort by NULL flag first, then by timestamp
    query = query.order_by(Concept.last_reviewed.is_(None), Concept.last_reviewed.asc()).limit(5)
    concepts = db.session.execute(query).scalars().all()

    events: List[ApplicationEvent] = []
    for concept in concepts:
        prompt_text = generate_single_application_prompt(concept, project)
        event = ApplicationEvent(
            user_id=user_id,
            concept_id=concept.id,
            project_id=project.id,
            prompted_at=datetime.utcnow(),
            prompt_text=prompt_text,
        )
        db.session.add(event)
        events.append(event)
    db.session.commit()
    return events


def get_pending_application_prompts(user_id: int, limit: int = 5) -> List[ApplicationEvent]:
    query = (
        db.select(ApplicationEvent)
        .filter(ApplicationEvent.user_id == user_id, ApplicationEvent.user_response.is_(None))
        .order_by(ApplicationEvent.prompted_at.desc())
        .limit(limit)
    )
    return db.session.execute(query).scalars().all()
