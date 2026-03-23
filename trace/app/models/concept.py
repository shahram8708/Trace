from datetime import datetime, date
from ..extensions import db


class Concept(db.Model):
    __tablename__ = "concepts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_item_id = db.Column(db.Integer, db.ForeignKey("source_items.id", ondelete="SET NULL"))
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    source_excerpt = db.Column(db.Text)
    domain_tag = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_reviewed = db.Column(db.DateTime)
    next_review_due = db.Column(db.Date)
    sm2_ease_factor = db.Column(db.Float, default=2.5, nullable=False)
    sm2_interval = db.Column(db.Integer, default=1, nullable=False)
    sm2_repetitions = db.Column(db.Integer, default=0, nullable=False)
    retention_strength = db.Column(db.Float, default=0.0, nullable=False)
    total_reviews = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_mature = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="concepts")
    source_item = db.relationship("SourceItem", back_populates="concepts")
    review_events = db.relationship("ReviewEvent", back_populates="concept", cascade="all, delete-orphan")
    connections_as_a = db.relationship(
        "ConceptConnection",
        foreign_keys="ConceptConnection.concept_a_id",
        back_populates="concept_a",
        cascade="all, delete-orphan",
    )
    connections_as_b = db.relationship(
        "ConceptConnection",
        foreign_keys="ConceptConnection.concept_b_id",
        back_populates="concept_b",
        cascade="all, delete-orphan",
    )

    @property
    def is_due(self) -> bool:
        if not self.next_review_due:
            return False
        return self.next_review_due <= date.today()
