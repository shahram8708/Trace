from datetime import datetime
from ..extensions import db


class SourceItem(db.Model):
    __tablename__ = "source_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(500))
    source_url = db.Column(db.String(2000))
    source_type = db.Column(db.String(50), nullable=False)
    full_text = db.Column(db.Text)
    import_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    domain_tags = db.Column(db.JSON)
    is_processed = db.Column(db.Boolean, default=False, nullable=False)
    concept_count = db.Column(db.Integer, default=0, nullable=False)
    cover_image_url = db.Column(db.String(2000))
    author = db.Column(db.String(300))
    word_count = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship("User", back_populates="source_items")
    concepts = db.relationship("Concept", back_populates="source_item")
    extraction_entries = db.relationship("AIExtractionQueue", back_populates="source_item", cascade="all, delete-orphan")
