from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, ValidationError
from wtforms.fields import EmailField

REVIEW_TIME_CHOICES = [
    ("06:00", "6:00 AM"),
    ("07:00", "7:00 AM"),
    ("08:00", "8:00 AM"),
    ("09:00", "9:00 AM"),
    ("10:00", "10:00 AM"),
    ("12:00", "12:00 PM"),
    ("13:00", "1:00 PM"),
    ("17:00", "5:00 PM"),
    ("18:00", "6:00 PM"),
    ("19:00", "7:00 PM"),
    ("20:00", "8:00 PM"),
    ("21:00", "9:00 PM"),
]


class ProfileEditForm(FlaskForm):
    first_name = StringField("First name", validators=[Length(max=100)])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Save Profile")


class NotificationPreferencesForm(FlaskForm):
    review_reminder_enabled = BooleanField("Daily review reminders", default=True)
    review_reminder_time = SelectField("Reminder time", choices=REVIEW_TIME_CHOICES, default="08:00")
    weekly_report_enabled = BooleanField("Weekly knowledge report email", default=True)
    application_reminders_enabled = BooleanField("Application reminder emails", default=True)
    submit = SubmitField("Save Preferences")


class DeleteAccountForm(FlaskForm):
    confirmation_text = StringField("Type DELETE MY ACCOUNT to confirm", validators=[DataRequired(), Length(max=50)])
    submit = SubmitField("Permanently Delete My Account")

    def validate_confirmation_text(self, field):
        if field.data != "DELETE MY ACCOUNT":
            raise ValidationError("You must type DELETE MY ACCOUNT exactly.")
