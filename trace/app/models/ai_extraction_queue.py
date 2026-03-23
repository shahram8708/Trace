from datetime import datetime
from ..extensions import db


class AIExtractionQueue(db.Model):
    __tablename__ = "ai_extraction_queue"

    id = db.Column(db.Integer, primary_key=True)
    source_item_id = db.Column(db.Integer, db.ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(50), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    extracted_concepts_json = db.Column(db.JSON)
    model_used = db.Column(db.String(100), default="gemini-2.5-flash", nullable=False)

    source_item = db.relationship("SourceItem", back_populates="extraction_entries")
