import ipaddress
from urllib.parse import urlparse
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectMultipleField
from wtforms.fields import URLField, FileField
from wtforms.validators import DataRequired, Length, Optional, URL, ValidationError

DOMAIN_CHOICES = [
    ("Product Management", "Product Management"),
    ("Software Engineering", "Software Engineering"),
    ("Data & Analytics", "Data & Analytics"),
    ("Leadership & Management", "Leadership & Management"),
    ("Marketing", "Marketing"),
    ("Finance & Investing", "Finance & Investing"),
    ("Design & UX", "Design & UX"),
    ("Science & Research", "Science & Research"),
    ("Psychology & Behavior", "Psychology & Behavior"),
    ("Business Strategy", "Business Strategy"),
    ("Communication & Writing", "Communication & Writing"),
    ("General Knowledge", "General Knowledge"),
]


def _is_private_host(host: str) -> bool:
    host_lower = host.lower()
    if host_lower in {"localhost", "127.0.0.1"}:
        return True
    try:
        ip = ipaddress.ip_address(host_lower)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        # Not an IP, check common private patterns
        private_prefixes = ("10.", "192.168.")
        if host_lower.startswith(private_prefixes):
            return True
        if host_lower.startswith("172."):
            try:
                second_octet = int(host_lower.split(".")[1])
                return 16 <= second_octet <= 31
            except (IndexError, ValueError):
                return False
    return False


class URLImportForm(FlaskForm):
    url = URLField("URL", validators=[DataRequired(), Length(max=2000), URL(require_tld=True, message="Enter a valid URL starting with http or https.")])
    domain_tags = SelectMultipleField("Domain Tags", choices=DOMAIN_CHOICES, validators=[Optional()])
    submit = SubmitField("Import Article")

    def validate_url(self, field):
        parsed = urlparse(field.data or "")
        if parsed.scheme not in {"http", "https"}:
            raise ValidationError("URL must start with http:// or https://")
        if not parsed.netloc:
            raise ValidationError("Enter a valid URL")
        if _is_private_host(parsed.hostname or ""):
            raise ValidationError("Local or private network URLs are not allowed.")


class TextImportForm(FlaskForm):
    title = StringField("Title or Topic", validators=[DataRequired(), Length(max=500)])
    content = TextAreaField(
        "Content",
        validators=[
            DataRequired(),
            Length(min=200, max=50000, message="Please paste at least 200 characters of content for meaningful concept extraction."),
        ],
    )
    author = StringField("Author", validators=[Optional(), Length(max=300)])
    domain_tags = SelectMultipleField("Domain Tags", choices=DOMAIN_CHOICES, validators=[Optional()])
    submit = SubmitField("Extract Concepts")


class PDFImportForm(FlaskForm):
    pdf_file = FileField("PDF File", validators=[DataRequired()])
    title = StringField("Title", validators=[Optional(), Length(max=500)])
    author = StringField("Author", validators=[Optional(), Length(max=300)])
    domain_tags = SelectMultipleField("Domain Tags", choices=DOMAIN_CHOICES, validators=[Optional()])
    submit = SubmitField("Process PDF")

    def validate_pdf_file(self, field):
        file_storage = field.data
        if not file_storage or not getattr(file_storage, "filename", ""):
            raise ValidationError("Please upload a PDF file.")
        filename = file_storage.filename.lower()
        if not filename.endswith(".pdf"):
            raise ValidationError("File must be a PDF.")


class KindleImportForm(FlaskForm):
    kindle_file = FileField("Kindle Highlights", validators=[DataRequired()])
    submit = SubmitField("Import Highlights")

    def validate_kindle_file(self, field):
        file_storage = field.data
        if not file_storage or not getattr(file_storage, "filename", ""):
            raise ValidationError("Please upload your Kindle export file.")
        filename = file_storage.filename.lower()
        if not (filename.endswith(".csv") or filename.endswith(".txt")):
            raise ValidationError("File must be a .csv or .txt Kindle export.")
