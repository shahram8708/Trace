import json
import re
import logging
import time
import traceback
from datetime import datetime

try:  # Optional dependency
    import markupsafe  # noqa: F401
    MARKUPSAFE_AVAILABLE = True
except Exception:  # pragma: no cover
    MARKUPSAFE_AVAILABLE = False

logger = logging.getLogger(__name__)


def _type_matches(parsed_obj, expected_type: str) -> bool:
    if expected_type == "array":
        return isinstance(parsed_obj, list)
    if expected_type == "object":
        return isinstance(parsed_obj, dict)
    return True


def extract_json_from_gemini_response(raw_text: str, expected_type: str = "any", context_label: str = "gemini_call"):
    print(f"\n{'='*60}")
    print(f"[GEMINI RAW RESPONSE] Context: {context_label}")
    print(f"[GEMINI RAW RESPONSE] Timestamp: {datetime.utcnow().isoformat()}")
    print(f"[GEMINI RAW RESPONSE] Response length: {len(raw_text) if raw_text is not None else 0} characters")
    print(f"[GEMINI RAW RESPONSE] First 500 chars:")
    preview = raw_text or ""
    print(preview[:500])
    print(f"[GEMINI RAW RESPONSE] Last 200 chars:")
    if preview:
        print(preview[-200:] if len(preview) > 200 else "(same as above)")
    else:
        print("(no content)")
    print(f"{'='*60}\n")
    logger.debug(f"[{context_label}] Full raw response: {preview}")

    if raw_text is None or not str(raw_text).strip():
        print(f"\n{'!'*60}")
        print(f"[GEMINI JSON PARSE FAILURE] Context: {context_label}")
        print(f"[GEMINI JSON PARSE FAILURE] Empty or None response received")
        print(f"{'!'*60}\n")
        logger.error(f"[{context_label}] Empty or None response from Gemini")
        return None

    stripped_text = str(raw_text).strip()

    # Strategy A: Direct parse
    try:
        direct_parsed = json.loads(stripped_text)
        if _type_matches(direct_parsed, expected_type):
            logger.debug(f"[{context_label}] Strategy A direct parse succeeded")
            return direct_parsed
        logger.debug(f"[{context_label}] Strategy A parsed but type mismatch; expected {expected_type}, got {type(direct_parsed)}")
    except Exception as exc:
        logger.debug(f"[{context_label}] Strategy A direct parse failed: {exc}")

    # Strategy B: Strip markdown wrappers
    markdown_variants = []
    markdown_variants.append(re.sub(r"^```json\s*", "", stripped_text, flags=re.IGNORECASE))
    markdown_variants[-1] = re.sub(r"\s*```$", "", markdown_variants[-1])

    markdown_variants.append(re.sub(r"^```\w*\s*", "", stripped_text))
    markdown_variants[-1] = re.sub(r"\s*```$", "", markdown_variants[-1])

    markdown_variants.append(re.sub(r"^`?json\s*", "", stripped_text, flags=re.IGNORECASE))
    markdown_variants[-1] = re.sub(r"`$", "", markdown_variants[-1])

    for idx, variant in enumerate(markdown_variants, start=1):
        try:
            parsed_variant = json.loads(variant.strip())
            if _type_matches(parsed_variant, expected_type):
                logger.debug(f"[{context_label}] Strategy B markdown strip succeeded on variant {idx}")
                return parsed_variant
            logger.debug(f"[{context_label}] Strategy B variant {idx} parsed but type mismatch")
        except Exception as exc:
            logger.debug(f"[{context_label}] Strategy B variant {idx} failed: {exc}")

    # Strategy C: Regex array extraction
    if expected_type in {"array", "any"}:
        array_match = re.search(r"\[.*\]", stripped_text, re.DOTALL)
        if array_match:
            try:
                array_parsed = json.loads(array_match.group())
                if _type_matches(array_parsed, expected_type):
                    logger.debug(f"[{context_label}] Strategy C regex array succeeded")
                    return array_parsed
                logger.debug(f"[{context_label}] Strategy C parsed but type mismatch")
            except Exception as exc:
                logger.debug(f"[{context_label}] Strategy C failed: {exc}")

    # Strategy D: Regex object extraction
    if expected_type in {"object", "any"}:
        object_match = re.search(r"\{.*\}", stripped_text, re.DOTALL)
        if object_match:
            try:
                obj_parsed = json.loads(object_match.group())
                if _type_matches(obj_parsed, expected_type):
                    logger.debug(f"[{context_label}] Strategy D regex object succeeded")
                    return obj_parsed
                logger.debug(f"[{context_label}] Strategy D parsed but type mismatch")
            except Exception as exc:
                logger.debug(f"[{context_label}] Strategy D failed: {exc}")

    # Strategy E: Bracket-based slice
    first_brace = stripped_text.find("{") if "{" in stripped_text else -1
    first_bracket = stripped_text.find("[") if "[" in stripped_text else -1
    start_indices = [i for i in [first_brace, first_bracket] if i >= 0]
    if start_indices:
        start_idx = min(start_indices)
        closing_char = "]" if stripped_text[start_idx] == "[" else "}"
        end_idx = stripped_text.rfind(closing_char)
        if end_idx > start_idx:
            candidate = stripped_text[start_idx : end_idx + 1]
            try:
                parsed_candidate = json.loads(candidate)
                if _type_matches(parsed_candidate, expected_type):
                    logger.debug(f"[{context_label}] Strategy E bracket slice succeeded")
                    return parsed_candidate
                logger.debug(f"[{context_label}] Strategy E parsed but type mismatch")
            except Exception as exc:
                logger.debug(f"[{context_label}] Strategy E failed: {exc}")

    # Strategy F: Line-by-line parsing
    for line_number, line in enumerate(stripped_text.splitlines(), start=1):
        try:
            parsed_line = json.loads(line.strip())
            if _type_matches(parsed_line, expected_type):
                logger.debug(f"[{context_label}] Strategy F succeeded on line {line_number}")
                return parsed_line
            logger.debug(f"[{context_label}] Strategy F line {line_number} parsed but type mismatch")
        except Exception as exc:
            logger.debug(f"[{context_label}] Strategy F line {line_number} failed: {exc}")

    print(f"\n{'!'*60}")
    print(f"[GEMINI JSON PARSE FAILURE] Context: {context_label}")
    print(f"[GEMINI JSON PARSE FAILURE] ALL 6 STRATEGIES FAILED")
    print(f"[GEMINI JSON PARSE FAILURE] Expected type: {expected_type}")
    print(f"[GEMINI JSON PARSE FAILURE] Raw response length: {len(stripped_text)}")
    print(f"[GEMINI JSON PARSE FAILURE] Full raw response below:")
    print(f"--- START RAW RESPONSE ---")
    print(stripped_text)
    print(f"--- END RAW RESPONSE ---")
    print(f"[GEMINI JSON PARSE FAILURE] Strategies attempted: Direct parse, Strip markdown, Regex array, Regex object, Bracket extraction, Line-by-line")
    print(f"{'!'*60}\n")
    logger.error(
        f"[{context_label}] JSON parse failed after all strategies. Expected {expected_type}. Raw: {stripped_text}",
        exc_info=False,
    )
    return None


def validate_json_structure(parsed_json, required_keys, context_label: str = "validation"):
    if parsed_json is None:
        print(f"[VALIDATION] Context: {context_label} | Input type: None | Items before validation: 0 | Items after validation: 0 | Removed: 0")
        return []

    removed_count = 0
    before_count = len(parsed_json) if isinstance(parsed_json, list) else 1

    if isinstance(parsed_json, list):
        validated = []
        for item in parsed_json:
            if not isinstance(item, dict):
                removed_count += 1
                continue
            missing = [k for k in required_keys if k not in item or item[k] in (None, "")]
            if missing:
                removed_count += 1
                continue
            validated.append(item)
        after_count = len(validated)
        print(
            f"[VALIDATION] Context: {context_label} | Input type: list | Items before validation: {before_count} | Items after validation: {after_count} | Removed: {removed_count}"
        )
        return validated

    if isinstance(parsed_json, dict):
        missing = [k for k in required_keys if k not in parsed_json or parsed_json[k] in (None, "")]
        if missing:
            logger.warning(f"[{context_label}] Missing keys in object: {missing}")
        print(
            f"[VALIDATION] Context: {context_label} | Input type: dict | Items before validation: {before_count} | Items after validation: {before_count} | Removed: {removed_count}"
        )
        return parsed_json

    print(
        f"[VALIDATION] Context: {context_label} | Input type: {type(parsed_json)} | Items before validation: {before_count} | Items after validation: 0 | Removed: {before_count}"
    )
    return []


def call_gemini_with_retry(prompt_text: str, context_label: str = "gemini", max_retries: int = 3, retry_delay: float = 2.0):
    current_delay = retry_delay
    for attempt in range(1, max_retries + 1):
        print(f"[GEMINI CALL] Context: {context_label} | Attempt: {attempt}/{max_retries}")
        print(
            f"[GEMINI CALL] Prompt length: {len(prompt_text)} chars | First 300 chars of prompt: {prompt_text[:300]}"
        )
        start_time = time.time()
        try:
            from google import genai

            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text,
            )
            elapsed = time.time() - start_time
            print(
                f"[GEMINI CALL] SUCCESS | Attempt: {attempt} | Elapsed: {elapsed:.2f}s | Response length: {len(response.text or '')}"
            )
            return response.text
        except Exception as e:  # pragma: no cover
            print(f"\n{'*'*60}")
            print(f"[GEMINI CALL ERROR] Context: {context_label}")
            print(f"[GEMINI CALL ERROR] Attempt: {attempt}/{max_retries}")
            print(f"[GEMINI CALL ERROR] Error type: {type(e).__name__}")
            print(f"[GEMINI CALL ERROR] Error message: {str(e)}")
            print(f"[GEMINI CALL ERROR] Full traceback:")
            print(traceback.format_exc())
            print(f"{'*'*60}\n")
            logger.error(f"[{context_label}] Gemini call error on attempt {attempt}", exc_info=True)
            if attempt < max_retries:
                print(f"[GEMINI CALL] Waiting {current_delay}s before retry...")
                time.sleep(current_delay)
                current_delay *= 2
            else:
                print(f"[GEMINI CALL FATAL] All {max_retries} attempts failed for context: {context_label}")
                return None


def call_gemini_with_search_and_retry(prompt_text: str, context_label: str = "gemini_search", max_retries: int = 3, retry_delay: float = 2.0):
    current_delay = retry_delay
    for attempt in range(1, max_retries + 1):
        print(f"[GEMINI CALL] Context: {context_label} | Attempt: {attempt}/{max_retries}")
        print(
            f"[GEMINI CALL] Prompt length: {len(prompt_text)} chars | First 300 chars of prompt: {prompt_text[:300]}"
        )
        start_time = time.time()
        try:
            from google import genai
            from google.genai import types

            client = genai.Client()
            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            config = types.GenerateContentConfig(tools=[grounding_tool])
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text,
                config=config,
            )
            elapsed = time.time() - start_time
            print(
                f"[GEMINI CALL] SUCCESS | Attempt: {attempt} | Elapsed: {elapsed:.2f}s | Response length: {len(response.text or '')}"
            )
            return response.text
        except Exception as e:  # pragma: no cover
            print(f"\n{'*'*60}")
            print(f"[GEMINI CALL ERROR] Context: {context_label}")
            print(f"[GEMINI CALL ERROR] Attempt: {attempt}/{max_retries}")
            print(f"[GEMINI CALL ERROR] Error type: {type(e).__name__}")
            print(f"[GEMINI CALL ERROR] Error message: {str(e)}")
            print(f"[GEMINI CALL ERROR] Full traceback:")
            print(traceback.format_exc())
            print(f"{'*'*60}\n")
            logger.error(f"[{context_label}] Gemini search call error on attempt {attempt}", exc_info=True)
            if attempt < max_retries:
                print(f"[GEMINI CALL] Waiting {current_delay}s before retry...")
                time.sleep(current_delay)
                current_delay *= 2
            else:
                print(f"[GEMINI CALL FATAL] All {max_retries} attempts failed for context: {context_label}")
                return None
