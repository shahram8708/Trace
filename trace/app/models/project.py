from datetime import datetime
from ..extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    domain_tags = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reminder_frequency = db.Column(db.String(50), default="weekly", nullable=False)

    user = db.relationship("User", back_populates="projects")
    application_events = db.relationship("ApplicationEvent", back_populates="project", cascade="all, delete-orphan")
