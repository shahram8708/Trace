from datetime import datetime
from sqlalchemy import UniqueConstraint
from ..extensions import db


class ConceptConnection(db.Model):
    __tablename__ = "concept_connections"
    __table_args__ = (UniqueConstraint("user_id", "concept_a_id", "concept_b_id", name="uq_connection_pair"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concept_a_id = db.Column(db.Integer, db.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    concept_b_id = db.Column(db.Integer, db.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    relationship_type = db.Column(db.String(100), nullable=False)
    connection_source = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    concept_a = db.relationship("Concept", foreign_keys=[concept_a_id], back_populates="connections_as_a")
    concept_b = db.relationship("Concept", foreign_keys=[concept_b_id], back_populates="connections_as_b")
    user = db.relationship("User", back_populates="concept_connections")
