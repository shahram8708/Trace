import json
import tempfile
import os
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.source_item import SourceItem
from ..models.ai_extraction_queue import AIExtractionQueue
from ..models.concept import Concept
from ..forms.import_forms import URLImportForm, TextImportForm, PDFImportForm, KindleImportForm
from ..services.content_fetcher import fetch_article_from_url, is_url_safe
from ..services.pdf_processor import validate_pdf_file, extract_text_from_pdf
from ..services.kindle_importer import parse_kindle_csv, build_kindle_source_text
from ..tasks import process_ai_extraction_async, compute_connection_suggestions_for_user
from ..utils.free_tier import check_free_tier_limits
from ..utils.decorators import onboarding_required

import_bp = Blueprint("import_bp", __name__, url_prefix="/import")


def _require_onboarding():
    if not current_user.onboarding_complete:
        return redirect(url_for("onboarding.step1"))
    return None


def _enqueue_extraction_entry(source_item):
    queue = AIExtractionQueue(source_item_id=source_item.id, status="pending")
    db.session.add(queue)
    db.session.commit()
    try:
        process_ai_extraction_async.delay(source_item.id)
    except Exception:  # pragma: no cover - defensive logging
        queue.status = "failed"
        queue.error_message = "Unable to enqueue extraction task."
        queue.completed_at = datetime.utcnow()
        db.session.commit()
    return queue


def _normalize_action(action: str) -> str:
    value = (action or "").strip().lower()
    if value in {"confirm", "confirmed", "accept", "accepted", "approve", "approved"}:
        return "confirm"
    if value in {"reject", "rejected", "decline", "declined"}:
        return "reject"
    return "pending"


def _normalize_extracted_concepts(queue, item_id: int):
    concepts_data = queue.extracted_concepts_json
    print(f"[IMPORT STATUS] Reading extracted_concepts_json for item_id={item_id}")
    print(f"[IMPORT STATUS] Type of stored value: {type(concepts_data)}")
    print(f"[IMPORT STATUS] Stored value preview: {str(concepts_data)[:300]}")
    print(f"[IMPORT STATUS] concepts_data type: {type(concepts_data)}")

    if concepts_data is None:
        print(f"[IMPORT STATUS] concepts_data is None — extraction may have failed")
        concepts_list = []
    elif isinstance(concepts_data, list):
        print(f"[IMPORT STATUS] concepts_data is already a list with {len(concepts_data)} items — no json.loads needed")
        concepts_list = concepts_data
    elif isinstance(concepts_data, str):
        print(f"[IMPORT STATUS] concepts_data is a string — attempting json.loads")
        try:
            concepts_list = json.loads(concepts_data)
            print(f"[IMPORT STATUS] json.loads succeeded — got {len(concepts_list)} items")
        except json.JSONDecodeError as e:
            print(f"[IMPORT STATUS] json.loads FAILED: {e}")
            print(f"[IMPORT STATUS] Raw string: {concepts_data[:500]}")
            concepts_list = []
    elif isinstance(concepts_data, dict):
        print(f"[IMPORT STATUS] concepts_data is a dict — checking for 'concepts' key")
        concepts_list = concepts_data.get("concepts", [])
    else:
        print(f"[IMPORT STATUS] concepts_data is unexpected type: {type(concepts_data)} — returning empty list")
        concepts_list = []

    return concepts_list


@import_bp.route("", methods=["GET"])
@login_required
def hub():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    limits = check_free_tier_limits(current_user)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    imports_this_month = (
        db.session.query(SourceItem)
        .filter(SourceItem.user_id == current_user.id, SourceItem.import_date >= thirty_days_ago)
        .count()
    )
    extractions_this_month = (
        db.session.query(AIExtractionQueue)
        .join(SourceItem, AIExtractionQueue.source_item_id == SourceItem.id)
        .filter(SourceItem.user_id == current_user.id, AIExtractionQueue.created_at >= thirty_days_ago)
        .count()
    )
    recent_imports = (
        SourceItem.query.filter_by(user_id=current_user.id)
        .order_by(SourceItem.import_date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "import_flow/hub.html",
        limits=limits,
        imports_this_month=imports_this_month,
        extractions_this_month=extractions_this_month,
        recent_imports=recent_imports,
    )


@import_bp.route("/url", methods=["GET", "POST"])
@login_required
def import_url():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    limits = check_free_tier_limits(current_user)
    form = URLImportForm()
    if request.method == "POST":
        if limits["import_limit_reached"] and not current_user.is_premium:
            flash("You've reached your monthly import limit. Upgrade to Pro for unlimited imports.", "warning")
            return redirect(url_for("import_bp.hub"))
        if limits["extraction_limit_reached"] and not current_user.is_premium:
            flash("You've reached your monthly AI extraction limit. Upgrade to continue.", "warning")
            return redirect(url_for("import_bp.hub"))
        if form.validate_on_submit():
            url_value = form.url.data
            if not is_url_safe(url_value):
                flash("This URL cannot be imported because it is not publicly accessible.", "danger")
                return render_template("import_flow/url.html", form=form, limits=limits)
            try:
                fetched = fetch_article_from_url(url_value)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("import_flow/url.html", form=form, limits=limits)

            source_item = SourceItem(
                user_id=current_user.id,
                title=fetched.get("title"),
                source_url=url_value,
                source_type="article",
                full_text=fetched.get("text"),
                domain_tags=form.domain_tags.data or [],
                is_processed=False,
                cover_image_url=fetched.get("cover_image_url"),
                author=fetched.get("author"),
                word_count=fetched.get("word_count", 0),
            )
            db.session.add(source_item)
            db.session.commit()
            _enqueue_extraction_entry(source_item)
            return redirect(url_for("import_bp.review", item_id=source_item.id))
    return render_template("import_flow/url.html", form=form, limits=limits)


@import_bp.route("/text", methods=["GET", "POST"])
@login_required
def import_text():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    limits = check_free_tier_limits(current_user)
    form = TextImportForm()
    if request.method == "POST":
        if limits["import_limit_reached"] and not current_user.is_premium:
            flash("You've reached your monthly import limit. Upgrade to Pro for unlimited imports.", "warning")
            return redirect(url_for("import_bp.hub"))
        if limits["extraction_limit_reached"] and not current_user.is_premium:
            flash("You've reached your monthly AI extraction limit. Upgrade to continue.", "warning")
            return redirect(url_for("import_bp.hub"))
        if form.validate_on_submit():
            word_count = len((form.content.data or "").split())
            if word_count < 50:
                flash("Please paste more content. Concept extraction requires at least 50 words.", "warning")
                return render_template("import_flow/text.html", form=form, limits=limits)
            source_item = SourceItem(
                user_id=current_user.id,
                title=form.title.data,
                source_type="text",
                full_text=form.content.data,
                domain_tags=form.domain_tags.data or [],
                author=form.author.data,
                word_count=word_count,
            )
            db.session.add(source_item)
            db.session.commit()
            _enqueue_extraction_entry(source_item)
            return redirect(url_for("import_bp.review", item_id=source_item.id))
    return render_template("import_flow/text.html", form=form, limits=limits)


@import_bp.route("/pdf", methods=["GET", "POST"])
@login_required
def import_pdf():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    limits = check_free_tier_limits(current_user)
    form = PDFImportForm()
    if request.method == "POST":
        if not current_user.is_premium:
            flash("PDF import is a Pro feature. Upgrade to unlock.", "warning")
            return redirect(url_for("main.pricing"))
        if form.validate_on_submit():
            upload = form.pdf_file.data
            if not upload:
                flash("Please upload a PDF.", "danger")
                return render_template("import_flow/pdf.html", form=form, limits=limits)
            try:
                validate_pdf_file(upload)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("import_flow/pdf.html", form=form, limits=limits)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file_path = temp_file.name
            upload.save(temp_file_path)
            try:
                extracted = extract_text_from_pdf(temp_file_path)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("import_flow/pdf.html", form=form, limits=limits)
            finally:
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass

            title = form.title.data or (upload.filename.rsplit(".", 1)[0] if upload.filename else "Untitled PDF")
            source_item = SourceItem(
                user_id=current_user.id,
                title=title,
                source_type="pdf",
                full_text=extracted["text"],
                domain_tags=form.domain_tags.data or [],
                author=form.author.data,
                word_count=extracted.get("word_count", 0),
            )
            db.session.add(source_item)
            db.session.commit()
            _enqueue_extraction_entry(source_item)
            return redirect(url_for("import_bp.review", item_id=source_item.id))
    return render_template("import_flow/pdf.html", form=form, limits=limits)


@import_bp.route("/kindle", methods=["GET", "POST"])
@login_required
def import_kindle():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    limits = check_free_tier_limits(current_user)
    form = KindleImportForm()
    if request.method == "POST":
        if not current_user.is_premium:
            flash("Kindle import is a Pro feature. Upgrade to unlock.", "warning")
            return redirect(url_for("main.pricing"))
        if form.validate_on_submit():
            upload = form.kindle_file.data
            if not upload:
                flash("Please upload your Kindle highlights file.", "danger")
                return render_template("import_flow/kindle.html", form=form, limits=limits)
            file_bytes = upload.read()
            try:
                books = parse_kindle_csv(file_bytes)
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("import_flow/kindle.html", form=form, limits=limits)

            created_items = []
            for book in books:
                combined_text = build_kindle_source_text(book)
                source_item = SourceItem(
                    user_id=current_user.id,
                    title=book.get("title"),
                    source_type="kindle",
                    full_text=combined_text,
                    domain_tags=[],
                    author=book.get("author"),
                    word_count=len(combined_text.split()),
                )
                db.session.add(source_item)
                db.session.flush()
                _enqueue_extraction_entry(source_item)
                created_items.append(source_item)
            db.session.commit()
            if len(created_items) == 1:
                return redirect(url_for("import_bp.review", item_id=created_items[0].id))
            return redirect(url_for("import_bp.kindle_results"))
    return render_template("import_flow/kindle.html", form=form, limits=limits)


@import_bp.route("/kindle-results", methods=["GET"])
@login_required
def kindle_results():
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    items = (
        SourceItem.query.filter_by(user_id=current_user.id, source_type="kindle")
        .order_by(SourceItem.import_date.desc())
        .limit(10)
        .all()
    )
    return render_template("import_flow/kindle_results.html", items=items)


@import_bp.route("/review/<int:item_id>", methods=["GET"])
@login_required
def review(item_id):
    onboarding_redirect = _require_onboarding()
    if onboarding_redirect:
        return onboarding_redirect
    source_item = SourceItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    extraction = AIExtractionQueue.query.filter_by(source_item_id=source_item.id).order_by(AIExtractionQueue.created_at.desc()).first()
    if not extraction or extraction.status in {"pending", "processing"}:
        return render_template("import_flow/processing.html", item=source_item)
    concepts = _normalize_extracted_concepts(extraction, item_id)
    status = extraction.status
    return render_template(
        "import_flow/review.html",
        source_item=source_item,
        concepts=concepts,
        status=status,
    )


@import_bp.route("/status/<int:item_id>", methods=["GET"])
@login_required
def status(item_id):
    source_item = SourceItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not source_item:
        return jsonify({"error": "not found"}), 404
    extraction = AIExtractionQueue.query.filter_by(source_item_id=source_item.id).order_by(AIExtractionQueue.created_at.desc()).first()
    if not extraction:
        return jsonify({"status": "pending", "concepts": [], "item_id": item_id})
    concepts = _normalize_extracted_concepts(extraction, item_id)
    return jsonify({"status": extraction.status, "concepts": concepts or [], "item_id": item_id})


@import_bp.route("/confirm/<int:item_id>", methods=["POST"])
@login_required
def confirm(item_id):
    source_item = SourceItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    extraction = AIExtractionQueue.query.filter_by(source_item_id=source_item.id).order_by(AIExtractionQueue.created_at.desc()).first()
    payload_raw = request.form.get("concepts_payload")
    print(f"\n[IMPORT CONFIRM] Received form data for item_id={item_id}")
    print(f"[IMPORT CONFIRM] Form keys: {list(request.form.keys())}")
    print(f"[IMPORT CONFIRM] Total form values: {len(request.form)}")
    if not payload_raw:
        flash("No concepts submitted.", "danger")
        return redirect(url_for("import_bp.review", item_id=item_id))
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        flash("Unable to process concepts. Please try again.", "danger")
        return redirect(url_for("import_bp.review", item_id=item_id))

    if not isinstance(payload, list):
        flash("Invalid concept submission.", "danger")
        return redirect(url_for("import_bp.review", item_id=item_id))

    normalized_payload = []
    for idx, concept in enumerate(payload, start=1):
        normalized_action = _normalize_action(concept.get("action"))
        concept_name = (concept.get("name") or "")[:50]
        print(f"[IMPORT CONFIRM] Processing concept {idx}: name='{concept_name}' | action={normalized_action}")
        normalized_payload.append({**concept, "action": normalized_action})

    payload = normalized_payload

    confirmed = [p for p in payload if p.get("action") == "confirm"]
    custom = [p for p in payload if p.get("is_custom")]
    rejected = [p for p in payload if p.get("action") == "reject"]
    total_to_add = len(confirmed)

    limits = check_free_tier_limits(current_user)
    remaining = limits.get("concepts_remaining") if limits.get("concepts_remaining") is not None else None
    blocked = 0
    if not current_user.is_premium and remaining is not None and total_to_add > remaining:
        blocked = total_to_add - remaining
        total_allowed = remaining
    else:
        total_allowed = total_to_add

    added = 0
    for item in payload:
        if item.get("action") != "confirm":
            continue
        if not current_user.is_premium and remaining is not None and added >= remaining:
            break
        name = (item.get("name") or "").strip()
        description = (item.get("description") or "").strip()
        domain_tag = (item.get("domain_tag") or "").strip()
        excerpt = (item.get("source_excerpt") or "").strip()
        if not name or not description:
            continue
        concept = Concept(
            user_id=current_user.id,
            source_item_id=source_item.id,
            name=name[:300],
            description=description[:2000],
            source_excerpt=excerpt[:1000],
            domain_tag=domain_tag,
            next_review_due=date.today() + timedelta(days=1),
            sm2_ease_factor=2.5,
            sm2_interval=1,
            sm2_repetitions=0,
            retention_strength=0.0,
        )
        db.session.add(concept)
        added += 1

    source_item.is_processed = True
    source_item.concept_count = added
    if extraction:
        extraction.status = extraction.status or "completed"
    db.session.commit()

    try:
        compute_connection_suggestions_for_user.delay(current_user.id)
    except Exception:  # pragma: no cover
        pass

    confirmed_count = len(confirmed)
    rejected_count = len(rejected)
    custom_count = len(custom)
    print(
        f"[IMPORT CONFIRM] COMPLETED | Confirmed: {confirmed_count} | Rejected: {rejected_count} | Custom: {custom_count} | Total saved to DB: {added}"
    )

    if blocked > 0:
        flash(
            f"You've reached your 50-concept limit. Upgrade to Pro for unlimited concepts. {blocked} concepts were not added.",
            "warning",
        )
    else:
        flash(f"{added} concepts added to your knowledge library! Your first review is scheduled for tomorrow.", "success")
    return redirect(url_for("dashboard_bp.dashboard"))
