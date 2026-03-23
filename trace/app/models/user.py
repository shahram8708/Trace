from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    subscription_tier = db.Column(db.String(50), default="free", nullable=False)
    subscription_expires = db.Column(db.DateTime)
    subscription_cancel_at = db.Column(db.DateTime)
    razorpay_customer_id = db.Column(db.String(100))
    razorpay_subscription_id = db.Column(db.String(100))
    review_reminder_time = db.Column(db.String(10))
    onboarding_complete = db.Column(db.Boolean, default=False, nullable=False)
    domains_of_interest = db.Column(db.JSON)
    preferred_content_types = db.Column(db.JSON)
    notifications_preferences = db.Column(db.JSON, default=dict)
    suggested_connections = db.Column(db.JSON, default=list)
    integration_waitlist = db.Column(db.JSON, default=dict)
    deletion_requested_at = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    total_reviews_completed = db.Column(db.Integer, default=0, nullable=False)
    current_streak_days = db.Column(db.Integer, default=0, nullable=False)
    longest_streak_days = db.Column(db.Integer, default=0, nullable=False)

    source_items = db.relationship("SourceItem", back_populates="user", cascade="all, delete-orphan")
    concepts = db.relationship("Concept", back_populates="user", cascade="all, delete-orphan")
    review_events = db.relationship("ReviewEvent", back_populates="user", cascade="all, delete-orphan")
    concept_connections = db.relationship(
        "ConceptConnection",
        foreign_keys="ConceptConnection.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    projects = db.relationship("Project", back_populates="user", cascade="all, delete-orphan")
    application_events = db.relationship("ApplicationEvent", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_display_name(self) -> str:
        if self.first_name:
            return self.first_name
        return (self.email.split("@", 1)[0]) if self.email else "User"

    def is_subscription_active(self) -> bool:
        if not self.is_premium:
            return False
        if self.subscription_expires is None:
            return True
        return self.subscription_expires > datetime.utcnow()

    @property
    def is_authenticated(self) -> bool:  # type: ignore[override]
        return True

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.is_verified)

    @property
    def is_anonymous(self) -> bool:  # type: ignore[override]
        return False

    def get_id(self):  # type: ignore[override]
        return str(self.id)

    @db.validates("email")
    def normalize_email(self, key, address):
        return address.lower() if address else address
