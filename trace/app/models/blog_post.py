from datetime import datetime
from ..extensions import db


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(200), default="Trace Team", nullable=False)
    published_at = db.Column(db.DateTime)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    meta_description = db.Column(db.String(300))
    cover_image_url = db.Column(db.String(2000))

    @property
    def is_live(self) -> bool:
        return self.is_published and (self.published_at is None or self.published_at <= datetime.utcnow())
