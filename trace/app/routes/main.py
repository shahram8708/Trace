from datetime import datetime, date
import textwrap
from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_login import login_required, current_user
from ..extensions import db, mail
from ..models.blog_post import BlogPost
from ..models.concept import Concept
from ..models.source_item import SourceItem
from ..utils.free_tier import check_free_tier_limits
from flask_mail import Message


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    subject = SelectField(
        "Subject",
        choices=[
            ("General Inquiry", "General Inquiry"),
            ("Technical Support", "Technical Support"),
            ("Billing", "Billing"),
            ("Partnership", "Partnership"),
            ("Press", "Press"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=20)])
    submit = SubmitField("Send Message")


main_bp = Blueprint("main", __name__)


def _send_contact_email(form):
    default_sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not default_sender:
        current_app.logger.error("MAIL_DEFAULT_SENDER or MAIL_USERNAME must be configured to send contact emails")
        return False

    msg = Message(
        subject=f"Contact: {form.subject.data}",
        sender=default_sender,
        recipients=[default_sender],
    )
    msg.body = (
        f"Name: {form.name.data}\n"
        f"Email: {form.email.data}\n"
        f"Subject: {form.subject.data}\n"
        f"Message:\n{form.message.data}"
    )
    msg.html = (
        f"<p><strong>Name:</strong> {form.name.data}</p>"
        f"<p><strong>Email:</strong> {form.email.data}</p>"
        f"<p><strong>Subject:</strong> {form.subject.data}</p>"
        f"<p><strong>Message:</strong><br>{form.message.data.replace('\n', '<br>')}</p>"
    )
    try:
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception("Failed to send contact email")
        return False


@main_bp.route("/")
def index():
    testimonials = [
        {
            "quote": "I used to read a book a month and remember almost nothing three months later. After using Trace for 60 days, I can actually recall and apply concepts from books I read six months ago.",
            "name": "Sarah M.",
            "role": "Product Director",
        },
        {
            "quote": "The concept extraction saves me hours. I import an article, AI pulls out the key ideas, I confirm them, and they're in my review queue. The daily sessions take 10 minutes and actually work.",
            "name": "Karan P.",
            "role": "Software Engineer",
        },
        {
            "quote": "I'm a consultant who reads constantly. Trace is the first tool that actually closes the loop between reading and professional application. It's transformed how I serve clients.",
            "name": "David L.",
            "role": "Management Consultant",
        },
    ]
    return render_template("main/index.html", testimonials=testimonials)


@main_bp.route("/about")
def about():
    return render_template("main/about.html")


@main_bp.route("/how-it-works")
def how_it_works():
    return render_template("main/how_it_works.html")


@main_bp.route("/pricing")
def pricing():
    plan_details = {
        "free": {
            "price": 0,
            "features": [
                "Up to 50 concepts",
                "5 source imports/month",
                "5 AI extractions/month",
                "Daily review queue",
                "Basic retention dashboard",
                "Browser extension access",
            ],
        },
        "pro_monthly": {"price": 999, "features": ["Unlimited everything"]},
        "pro_annual": {"price": 8999, "features": ["Unlimited everything", "Best value"]},
        "team": {
            "small": 7499,
            "business": 22999,
        },
    }
    razorpay_key_id = current_app.config.get("RAZORPAY_KEY_ID", "")
    return render_template("main/pricing.html", plan_details=plan_details, razorpay_key_id=razorpay_key_id)


@main_bp.route("/markdown-demo")
def markdown_demo():
    demo_markdown = textwrap.dedent(
        """
        # Markdown Playground
        ## Feature Tour
        ### Subheading Level 3
        #### Subheading Level 4

        Welcome to the **Markdown Rendering Demo**. This line shows *italic* text and ***bold italic*** text together. Here is `inline code` inside a sentence and a reference to an abbreviation HTML.

        - Bullet one
          - Nested bullet
            - Third-level bullet
        - Bullet two

        1. First ordered item
        2. Second ordered item
           1. Nested ordered
           2. Another nested
        3. Third ordered item

        > A thoughtful blockquote with a second line for emphasis.

        ```python
        def greet(name: str) -> str:
            message = f"Hello, {name}!"
            return message


        if __name__ == "__main__":
            print(greet("Trace"))
        ```

        | Column A | Column B | Column C |
        | --- | --- | --- |
        | Row 1 | Value | 123 |
        | Row 2 | **Bold Cell** | 456 |
        | Row 3 | *Italic Cell* | 789 |

        ---

        Here is a link to [Trace](https://example.com) and another to [Python](https://www.python.org).

        - [x] Ship the Markdown system
        - [ ] Write more docs
        - [ ] Celebrate launch

        Term Alpha
        : Definition for alpha.
        Term Beta
        : Definition for beta with more detail.

        This sentence uses an abbreviation: HTML and a footnote reference[^1].

        *[HTML]: HyperText Markup Language

        [^1]: This footnote explains the reference used above.
        """
    ).strip()

    sample_plain = "This is plain text without markdown syntax."

    return render_template(
        "demo/markdown_demo.html",
        content=demo_markdown,
        show_toc=True,
        page_title="Markdown Rendering Demo",
        use_markdown=True,
        some_variable=sample_plain,
    )


@main_bp.route("/blog")
def blog_index():
    page = request.args.get("page", 1, type=int)
    query = db.select(BlogPost).filter(BlogPost.is_published.is_(True)).order_by(BlogPost.published_at.desc())
    pagination = db.paginate(query, page=page, per_page=10, error_out=False)
    return render_template("main/blog_index.html", pagination=pagination, posts=pagination.items)


@main_bp.route("/blog/<slug>")
def blog_post(slug):
    post = db.session.execute(
        db.select(BlogPost).filter(BlogPost.slug == slug, BlogPost.is_published.is_(True))
    ).scalar_one_or_none()
    if not post:
        return render_template("errors/404.html"), 404
    related = db.session.execute(
        db.select(BlogPost)
        .filter(BlogPost.id != post.id, BlogPost.is_published.is_(True))
        .order_by(BlogPost.published_at.desc())
        .limit(3)
    ).scalars().all()
    return render_template("main/blog_post.html", post=post, related_posts=related)


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        sent = _send_contact_email(form)
        if sent:
            flash("Thanks for reaching out! We respond within 24 hours.", "success")
        else:
            flash("We couldn't send your message right now. Please try again soon.", "danger")
        return redirect(url_for("main.contact"))
    return render_template("main/contact.html", form=form)


@main_bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@main_bp.route("/terms")
def terms():
    return render_template("legal/terms.html")

