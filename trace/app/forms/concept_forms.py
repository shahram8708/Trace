from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length


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


class ConceptEditForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=300)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=20, max=2000)])
    domain_tag = SelectField("Domain", choices=DOMAIN_CHOICES, validators=[DataRequired()])
    source_excerpt = TextAreaField("Source Excerpt (optional)", validators=[Length(max=1000)])
    submit = SubmitField("Save Changes")
