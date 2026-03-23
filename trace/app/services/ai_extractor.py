import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List
from ..utils.gemini_parser import (
    call_gemini_with_retry,
    extract_json_from_gemini_response,
    validate_json_structure,
)

logger = logging.getLogger(__name__)


def extract_concepts_from_text(content_text: str, domain_tags: List[str] | None = None, source_title: str | None = None) -> List[Dict[str, str]]:
    function_label = "extract_concepts_from_text"
    print(
        f"\n[{function_label}] STARTED | Params: content_length={len(content_text or '')} | domain_tags_count={len(domain_tags or [])} | source_title_present={bool(source_title)}"
    )

    try:
        truncated = (content_text or "")[:8000]
        if content_text and len(content_text) > 8000:
            truncated += "\n\n[Note: Source text truncated for processing]"

        audience_context = f"User focuses on domains: {', '.join(domain_tags)}." if domain_tags else ""
        title_context = f"Source title: {source_title}." if source_title else ""

        prompt = f"""
You are a knowledge extraction system. Extract 3-8 standalone, transferable concepts that a professional can apply.
Focus on frameworks, principles, mental models, actionable insights, and important distinctions.
Each concept must stand alone without the source text. Avoid generic summaries, trivial facts, plot points, or unsupported opinions.

Source text:
{truncated}

{audience_context}
{title_context}

CRITICAL OUTPUT REQUIREMENT:
You must respond with ONLY a valid JSON array. No introduction text. No explanation. No markdown formatting. No code blocks. No backticks. The very first character of your response must be [ and the very last character must be ].

EXACT FORMAT REQUIRED — your response must look exactly like this example:
[
    {{
        "name": "Spaced Repetition Effect",
        "description": "Learning is significantly more durable when review sessions are spaced over time rather than massed together. Each retrieval attempt strengthens the memory trace and extends the interval before the next review is needed.",
        "source_excerpt": "Research consistently shows that distributing practice across multiple sessions produces better long-term retention than cramming the same amount of practice into a single session."
    }},
    {{
        "name": "Desirable Difficulty Principle",
        "description": "Introducing manageable challenges during learning — such as retrieval practice, interleaving, and spacing — improves long-term retention even though they may slow initial acquisition.",
        "source_excerpt": "When learning feels difficult and slow, it is often a sign that deep processing is occurring and that the material will be retained better."
    }}
]

RULES FOR YOUR JSON RESPONSE:
1. Start with [ immediately — no text before it
2. End with ] immediately — no text after it
3. Each object must have exactly these 3 keys: "name", "description", "source_excerpt"
4. All values must be strings (no null, no numbers, no nested objects)
5. "name" must be 3-7 words maximum
6. "description" must be 1-3 complete sentences
7. "source_excerpt" must be 1-3 sentences copied verbatim from the source text
8. Minimum 3 concepts, maximum 8 concepts
9. Do NOT wrap in ```json``` or any markdown
"""

        response_text = call_gemini_with_retry(prompt, context_label="concept_extraction")
        if response_text is None:
            return []

        parsed = extract_json_from_gemini_response(
            response_text,
            expected_type="array",
            context_label="concept_extraction",
        )
        validated = validate_json_structure(
            parsed,
            required_keys=["name", "description", "source_excerpt"],
            context_label="concept_extraction",
        )

        cleaned_concepts: List[Dict[str, str]] = []
        for item in validated:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            excerpt = str(item.get("source_excerpt", "")).strip()
            if not (name and description and excerpt):
                continue
            cleaned_concepts.append(
                {
                    "name": name[:300],
                    "description": description[:2000],
                    "source_excerpt": excerpt[:1000],
                }
            )

        print(
            f"[{function_label}] COMPLETED SUCCESSFULLY | Result: {len(cleaned_concepts)} concepts extracted at {datetime.utcnow().isoformat()}"
        )
        return cleaned_concepts

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
        return []

    except AttributeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] ATTRIBUTE ERROR (likely response.text is None or response object is unexpected)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] AttributeError: {e}", exc_info=True)
        return []

    except TypeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] TYPE ERROR (likely json.loads received wrong type)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] TypeError: {e}", exc_info=True)
        return []

    except Exception as e:  # pragma: no cover
        print(f"\n{'!'*60}")
        print(f"[{function_label}] UNEXPECTED ERROR")
        print(f"[{function_label}] Error type: {type(e).__name__}")
        print(f"[{function_label}] Error message: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] Unexpected error: {e}", exc_info=True)
        return []


def suggest_ai_concept_connections(concepts_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    function_label = "suggest_ai_concept_connections"
    print(
        f"\n[{function_label}] STARTED | Params: concept_count={len(concepts_list or [])}"
    )

    try:
        if not concepts_list:
            print(f"[{function_label}] COMPLETED SUCCESSFULLY | Result: 0 suggestions (no concepts provided)")
            return []

        limited = (concepts_list or [])[:50]
        concept_lines = []
        for c in limited:
            concept_lines.append(
                f"- id: {c.get('id')} | name: {c.get('name')} | description: {c.get('description','')}"
            )

        prompt = f"""
Identify meaningful relationships between these concepts. Relationship types must be one of: builds on, contradicts, applies to, example of, related to.
Return up to 10 suggestions as a JSON array with keys: concept_a_id, concept_b_id, relationship_type, reason (1 sentence).
Concepts:\n{chr(10).join(concept_lines)}

CRITICAL OUTPUT REQUIREMENT:
Respond with ONLY a valid JSON array. The first character must be [ and the last must be ]. No text before or after. No markdown. No backticks. No code blocks.

EXACT FORMAT REQUIRED — your response must look exactly like this:
[
  {
    "concept_a_id": 12,
    "concept_b_id": 47,
    "relationship_type": "builds on",
    "reason": "Concept A establishes the foundational principle that Concept B extends into a practical application framework."
  },
  {
    "concept_a_id": 23,
    "concept_b_id": 31,
    "relationship_type": "contradicts",
    "reason": "These two concepts present opposing views on how memory consolidation occurs during sleep."
  }
]

RULES:
1. Use only these relationship_type values: "builds on", "contradicts", "applies to", "example of", "related to"
2. concept_a_id and concept_b_id must be integers matching the IDs provided above
3. reason must be exactly 1 sentence
4. Maximum 10 suggestions
5. First character: [ Last character: ]
6. No markdown wrapping of any kind
"""

        response_text = call_gemini_with_retry(prompt, context_label="connection_suggestions")
        if response_text is None:
            return []

        parsed = extract_json_from_gemini_response(
            response_text,
            expected_type="array",
            context_label="connection_suggestions",
        )
        validated = validate_json_structure(
            parsed,
            required_keys=["concept_a_id", "concept_b_id", "relationship_type", "reason"],
            context_label="connection_suggestions",
        )

        suggestions: List[Dict[str, Any]] = []
        for item in validated[:10]:
            if not isinstance(item, dict):
                continue
            rel = item.get("relationship_type")
            if rel not in {"builds on", "contradicts", "applies to", "example of", "related to"}:
                continue
            suggestions.append(
                {
                    "concept_a_id": item.get("concept_a_id"),
                    "concept_b_id": item.get("concept_b_id"),
                    "relationship_type": rel,
                    "reason": str(item.get("reason", ""))[:240],
                }
            )

        print(
            f"[{function_label}] COMPLETED SUCCESSFULLY | Result: {len(suggestions)} connection suggestions"
        )
        return suggestions

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
        return []

    except AttributeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] ATTRIBUTE ERROR (likely response.text is None or response object is unexpected)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] AttributeError: {e}", exc_info=True)
        return []

    except TypeError as e:
        print(f"\n{'!'*60}")
        print(f"[{function_label}] TYPE ERROR (likely json.loads received wrong type)")
        print(f"[{function_label}] Error: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] TypeError: {e}", exc_info=True)
        return []

    except Exception as e:  # pragma: no cover
        print(f"\n{'!'*60}")
        print(f"[{function_label}] UNEXPECTED ERROR")
        print(f"[{function_label}] Error type: {type(e).__name__}")
        print(f"[{function_label}] Error message: {str(e)}")
        print(f"[{function_label}] Full traceback:")
        print(traceback.format_exc())
        print(f"{'!'*60}\n")
        logger.error(f"[{function_label}] Unexpected error: {e}", exc_info=True)
        return []
