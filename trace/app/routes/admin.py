import os
import re
from datetime import datetime, timedelta

import redis
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy import func, or_

from ..extensions import db
from ..models.user import User
from ..models.concept import Concept
from ..models.review_event import ReviewEvent
from ..models.ai_extraction_queue import AIExtractionQueue
from ..models.source_item import SourceItem
from ..models.blog_post import BlogPost
from ..utils.decorators import admin_required
from ..utils.tokens import generate_verification_token
from ..services.email_service import send_verification_email

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


@admin_bp.route("", methods=["GET"])
@login_required
@admin_required
def panel():
    total_users = User.query.count()
    verified_users = User.query.filter_by(is_verified=True).count()
    premium_users = User.query.filter_by(is_premium=True).count()
    monthly = User.query.filter(User.subscription_tier == "monthly", User.is_premium.is_(True)).count()
    annual = User.query.filter(User.subscription_tier == "annual", User.is_premium.is_(True)).count()
    mrr = round((monthly * 999) + (annual * (8999 / 12)))

    total_concepts = Concept.query.count()
    total_reviews = ReviewEvent.query.count()
    recent_reviews = ReviewEvent.query.filter(ReviewEvent.reviewed_at >= datetime.utcnow() - timedelta(days=7)).count()

    new_signups = (
        User.query.filter(User.created_at >= datetime.utcnow() - timedelta(days=7))
        .order_by(User.created_at.desc())
        .all()
    )

    failed_extractions = (
        AIExtractionQueue.query.filter(
            AIExtractionQueue.status == "failed",
            AIExtractionQueue.created_at >= datetime.utcnow() - timedelta(days=7),
        )
        .order_by(AIExtractionQueue.created_at.desc())
        .all()
    )

    queue_size = "N/A"
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis_client = redis.from_url(redis_url)
            queue_size = redis_client.llen("celery")
        except Exception:
            queue_size = "N/A"

    return render_template(
        "admin/panel.html",
        total_users=total_users,
        verified_users=verified_users,
        premium_users=premium_users,
        monthly=monthly,
        annual=annual,
        mrr=mrr,
        total_concepts=total_concepts,
        total_reviews=total_reviews,
        recent_reviews=recent_reviews,
        new_signups=new_signups,
        failed_extractions=failed_extractions,
        queue_size=queue_size,
    )


@admin_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def users():
    search = request.args.get("search", "").strip()
    tier = request.args.get("tier")
    sort = request.args.get("sort", "created")
    page = int(request.args.get("page", 1))

    query = User.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.email.ilike(like), User.first_name.ilike(like)))
    if tier in {"free", "monthly", "annual"}:
        query = query.filter(User.subscription_tier == tier)

    if sort == "last_login":
        query = query.order_by(User.last_login.desc().nullslast())
    elif sort == "concepts":
        query = query.outerjoin(Concept).group_by(User.id).order_by(func.count(Concept.id).desc())
    else:
        query = query.order_by(User.created_at.desc())

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    users_list = pagination.items
    concept_counts = dict(
        db.session.query(Concept.user_id, func.count(Concept.id)).group_by(Concept.user_id).all()
    )

    return render_template(
        "admin/users.html",
        users=users_list,
        pagination=pagination,
        concept_counts=concept_counts,
        search=search,
        tier=tier,
        sort=sort,
    )


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
@admin_required
def user_detail(user_id: int):
    user = User.query.get_or_404(user_id)
    concept_count = Concept.query.filter_by(user_id=user.id).count()
    review_count = ReviewEvent.query.filter_by(user_id=user.id).count()
    recent_sources = SourceItem.query.filter_by(user_id=user.id).order_by(SourceItem.import_date.desc()).limit(5).all()
    recent_reviews = ReviewEvent.query.filter_by(user_id=user.id).order_by(ReviewEvent.reviewed_at.desc()).limit(5).all()
    return render_template(
        "admin/user_detail.html",
        user=user,
        concept_count=concept_count,
        review_count=review_count,
        recent_sources=recent_sources,
        recent_reviews=recent_reviews,
    )


@admin_bp.route("/users/<int:user_id>/grant-premium", methods=["POST"])
@login_required
@admin_required
def grant_premium(user_id: int):
    user = User.query.get_or_404(user_id)
    user.is_premium = True
    user.subscription_tier = "monthly"
    user.subscription_expires = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash(f"Premium granted to {user.email}.", "success")
    return redirect(url_for("admin_bp.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/revoke-premium", methods=["POST"])
@login_required
@admin_required
def revoke_premium(user_id: int):
    user = User.query.get_or_404(user_id)
    user.is_premium = False
    user.subscription_tier = "free"
    user.subscription_expires = None
    db.session.commit()
    flash(f"Premium revoked from {user.email}.", "info")
    return redirect(url_for("admin_bp.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/resend-verify", methods=["POST"])
@login_required
@admin_required
def resend_verify(user_id: int):
    user = User.query.get_or_404(user_id)
    token = generate_verification_token(user.email)
    send_verification_email(user, token)
    flash(f"Verification email sent to {user.email}.", "success")
    return redirect(url_for("admin_bp.user_detail", user_id=user.id))


@admin_bp.route("/content", methods=["GET"])
@login_required
@admin_required
def content():
    posts = BlogPost.query.order_by(BlogPost.published_at.desc().nullslast()).all()
    return render_template("admin/blog_editor.html", posts=posts, editing=None)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return slug or "post"


@admin_bp.route("/content/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "Untitled").strip()
        slug = request.form.get("slug") or _slugify(title)
        content_body = request.form.get("content", "")
        author = request.form.get("author") or "Trace Team"
        meta_description = request.form.get("meta_description")
        cover_image_url = request.form.get("cover_image_url") or None
        is_published = bool(request.form.get("is_published"))

        existing = BlogPost.query.filter_by(slug=slug).first()
        if existing:
            flash("Slug already exists. Choose another.", "danger")
            return redirect(url_for("admin_bp.new_post"))

        post = BlogPost(
            title=title,
            slug=slug,
            content=content_body,
            author=author,
            meta_description=meta_description,
            cover_image_url=cover_image_url,
            is_published=is_published,
            published_at=datetime.utcnow() if is_published else None,
        )
        db.session.add(post)
        db.session.commit()
        flash("Blog post created.", "success")
        return redirect(url_for("admin_bp.content"))
    return render_template("admin/blog_editor.html", editing=None)


@admin_bp.route("/content/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_post(post_id: int):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == "POST":
        post.title = request.form.get("title", post.title)
        post.slug = request.form.get("slug") or _slugify(post.title)
        post.content = request.form.get("content", post.content)
        post.author = request.form.get("author") or post.author
        post.meta_description = request.form.get("meta_description") or post.meta_description
        post.cover_image_url = request.form.get("cover_image_url") or None
        post.is_published = bool(request.form.get("is_published"))
        if post.is_published and not post.published_at:
            post.published_at = datetime.utcnow()
        db.session.commit()
        flash("Post updated.", "success")
        return redirect(url_for("admin_bp.content"))
    return render_template("admin/blog_editor.html", editing=post)


@admin_bp.route("/content/<int:post_id>/publish", methods=["POST"])
@login_required
@admin_required
def toggle_publish(post_id: int):
    post = BlogPost.query.get_or_404(post_id)
    post.is_published = not post.is_published
    if post.is_published:
        post.published_at = post.published_at or datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "new_status": "published" if post.is_published else "draft"})
