"""initial_schema_14_tables

Revision ID: 16f2b4b4fa64
Revises: 
Create Date: 2026-08-04 18:38:42.339227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '16f2b4b4fa64'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    # 1. Categories
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Creators (Central Entity)
    op.create_table(
        "creators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("audience_bucket", sa.Integer(), nullable=True, index=True),
        sa.Column("creator_type", sa.String(100), nullable=True, index=True),
        sa.Column("creator_type_confidence", sa.Float(), nullable=True),
        sa.Column("creator_type_method", sa.Enum("rule", "llm", "manual", name="detectionmethod"), nullable=True),
        sa.Column("primary_language", sa.String(100), nullable=True, index=True),
        sa.Column("language_confidence", sa.Float(), nullable=True),
        sa.Column("language_method", sa.Enum("rule", "llm", "manual", name="detectionmethod", create_type=False), nullable=True),
        sa.Column("primary_category", sa.String(100), nullable=True, index=True),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", "DORMANT", "SUSPENDED", "PRIVATE", name="creatorstatus"), default="ACTIVE", nullable=False, index=True),
        sa.Column("influencer_score", sa.Float(), nullable=True, index=True),
        sa.Column("score_breakdown", json_type, nullable=True),
        sa.Column("needs_review", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Platform Profiles
    op.create_table(
        "platform_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("platform_user_id", sa.String(500), nullable=False),
        sa.Column("username", sa.String(500), nullable=True),
        sa.Column("display_name", sa.String(500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("following", sa.Integer(), nullable=True),
        sa.Column("video_count", sa.Integer(), nullable=True),
        sa.Column("verified", sa.Boolean(), default=False),
        sa.Column("profile_url", sa.String(1000), nullable=True),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_data", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform", "platform_user_id", name="uq_platform_user"),
    )
    op.create_index("ix_platform_profiles_creator", "platform_profiles", ["creator_id"])

    # 4. Videos
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform_profile_id", sa.Integer(), sa.ForeignKey("platform_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.String(500), nullable=False, index=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("duration", sa.String(50), nullable=True),
        sa.Column("is_short", sa.Boolean(), default=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("raw_payload", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform_profile_id", "video_id", name="uq_video"),
    )

    # 5. Posts
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform_profile_id", sa.Integer(), sa.ForeignKey("platform_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(500), nullable=False, index=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("post_type", sa.Enum("POST", "REEL", "STORY", "CAROUSEL", name="posttype"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("raw_payload", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform_profile_id", "post_id", name="uq_post"),
    )

    # 6. Engagement Metrics
    op.create_table(
        "engagement_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform_profile_id", sa.Integer(), sa.ForeignKey("platform_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avg_views", sa.Float(), nullable=True),
        sa.Column("avg_likes", sa.Float(), nullable=True),
        sa.Column("avg_comments", sa.Float(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("upload_frequency_per_month", sa.Float(), nullable=True),
        sa.Column("last_upload_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shorts_ratio", sa.Float(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. Social Links
    op.create_table(
        "social_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("value", sa.String(500), nullable=True),
        sa.Column("extracted_from", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("creator_id", "platform", "value", name="uq_social_link"),
    )
    op.create_index("ix_social_links_creator", "social_links", ["creator_id"])

    # 8. Broker Associations
    op.create_table(
        "broker_associations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_name", sa.String(200), nullable=False, index=True),
        sa.Column("relationship_type", sa.Enum("affiliate", "referral", "brand_ambassador", "sponsored", "past_partner", "mention_only", name="brokerrelationshiptype"), nullable=True),
        sa.Column("confidence", sa.Float(), default=0.0, nullable=False),
        sa.Column("detection_method", sa.Enum("rule", "llm", "manual", name="detectionmethod", create_type=False), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("evidence_urls", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 9. Creator Categories
    op.create_table(
        "creator_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), default=False, nullable=False),
        sa.Column("content_percentage", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("detection_method", sa.Enum("rule", "llm", "manual", name="detectionmethod", create_type=False), nullable=True),
        sa.UniqueConstraint("creator_id", "category_id", name="uq_creator_category"),
    )
    op.create_index("ix_creator_categories_category", "creator_categories", ["category_id"])

    # 10. Creator Relationships (Graph)
    op.create_table(
        "creator_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=True),
        sa.Column("target_platform_id", sa.String(500), nullable=True),
        sa.Column("relationship_type", sa.Enum("featured", "collaboration", "mention", "reply", "playlist", name="relationshiptype"), nullable=False),
        sa.Column("evidence_url", sa.String(1000), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_creator_rel_source", "creator_relationships", ["source_creator_id"])
    op.create_index("ix_creator_rel_target", "creator_relationships", ["target_creator_id"])

    # 11. Scrape Jobs
    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.Enum("youtube", "instagram", "full", "manual", name="scrapejobtype"), nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "completed", "failed", "cancelled", name="scrapejobstatus"), default="queued", nullable=False),
        sa.Column("keywords", json_type, nullable=True),
        sa.Column("total_discovered", sa.Integer(), default=0),
        sa.Column("total_processed", sa.Integer(), default=0),
        sa.Column("total_new", sa.Integer(), default=0),
        sa.Column("total_updated", sa.Integer(), default=0),
        sa.Column("discovery_depth", sa.Integer(), default=1),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 12. Scrape Logs
    op.create_table(
        "scrape_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scrape_job_id", sa.Integer(), sa.ForeignKey("scrape_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("keyword", sa.String(500), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("api_units_used", sa.Integer(), default=0),
        sa.Column("items_found", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 13. LLM Logs
    op.create_table(
        "llm_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task", sa.String(100), nullable=False),
        sa.Column("model_used", sa.String(200), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("parsed_result", json_type, nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("evidence", json_type, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_logs")
    op.drop_table("scrape_logs")
    op.drop_table("scrape_jobs")
    op.drop_table("creator_relationships")
    op.drop_table("creator_categories")
    op.drop_table("broker_associations")
    op.drop_table("social_links")
    op.drop_table("engagement_metrics")
    op.drop_table("posts")
    op.drop_table("videos")
    op.drop_table("platform_profiles")
    op.drop_table("creators")
    op.drop_table("categories")
