from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from .concept_forms import DOMAIN_CHOICES


class ProjectForm(FlaskForm):
    name = StringField("Project Name", validators=[DataRequired(), Length(max=300)])
    description = TextAreaField("Project Description (helps match relevant concepts)", validators=[Optional(), Length(max=1000)])
    domain_tags = SelectMultipleField("Relevant Knowledge Domains", choices=DOMAIN_CHOICES, validators=[Optional()])
    reminder_frequency = SelectField(
        "Reminder Frequency",
        choices=[("daily", "Daily"), ("weekly", "Weekly"), ("before_focus_time", "Before My Focus Time")],
        default="weekly",
    )
    is_active = BooleanField("Enable application reminders for this project", default=True)
    submit = SubmitField("Save Project")
