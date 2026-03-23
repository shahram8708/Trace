from datetime import datetime
from ..extensions import db


class ReviewEvent(db.Model):
    __tablename__ = "review_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    quality_rating = db.Column(db.Integer, nullable=False)
    user_response_text = db.Column(db.Text)
    previous_interval = db.Column(db.Integer)
    new_interval = db.Column(db.Integer)
    session_id = db.Column(db.String(50))

    user = db.relationship("User", back_populates="review_events")
    concept = db.relationship("Concept", back_populates="review_events")
