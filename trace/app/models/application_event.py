from datetime import datetime
from ..extensions import db


class ApplicationEvent(db.Model):
    __tablename__ = "application_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    prompted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    prompt_text = db.Column(db.Text)
    user_response = db.Column(db.String(50))
    responded_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="application_events")
    concept = db.relationship("Concept", backref=db.backref("application_events", cascade="all, delete-orphan"))
    project = db.relationship("Project", back_populates="application_events")
