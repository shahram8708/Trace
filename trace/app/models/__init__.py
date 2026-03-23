from sqlalchemy import Index
from .user import User
from .source_item import SourceItem
from .concept import Concept
from .review_event import ReviewEvent
from .connection import ConceptConnection
from .project import Project
from .application_event import ApplicationEvent
from .ai_extraction_queue import AIExtractionQueue
from .blog_post import BlogPost
from ..extensions import db

Index("ix_concepts_user_next_due", Concept.user_id, Concept.next_review_due, postgresql_where=(Concept.is_active.is_(True)))
Index("ix_review_events_user_time", ReviewEvent.user_id, ReviewEvent.reviewed_at)
Index("ix_review_events_concept", ReviewEvent.concept_id)
Index("ix_source_items_user_import", SourceItem.user_id, SourceItem.import_date)
Index("ix_concepts_user_domain", Concept.user_id, Concept.domain_tag)
Index("ix_connections_concept_a", ConceptConnection.concept_a_id)
Index("ix_connections_concept_b", ConceptConnection.concept_b_id)
