"""增加真实错因、变式题和复习计划。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_learning",
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("actual_error_reason", sa.String(32)),
        sa.Column("actual_error_note", sa.Text()),
        sa.Column("mastery_status", sa.String(20), nullable=False),
        sa.Column("starred", sa.Boolean(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_learning_mastery_status", "question_learning", ["mastery_status"])
    op.create_index("ix_question_learning_starred", "question_learning", ["starred"])
    op.create_index("ix_question_learning_next_review_at", "question_learning", ["next_review_at"])
    op.execute(
        """
        INSERT INTO question_learning (
            question_id, mastery_status, starred, review_count,
            next_review_at, created_at, updated_at
        )
        SELECT DISTINCT question_id, 'new', 0, 0,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM analysis_runs WHERE status = 'completed'
        """
    )

    op.create_table(
        "variation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_run_id",
            sa.String(36),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_config_id",
            sa.String(36),
            sa.ForeignKey("provider_configs.id", ondelete="SET NULL"),
        ),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("output_json", sa.JSON()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_variation_runs_question_id", "variation_runs", ["question_id"])
    op.create_index("ix_variation_runs_status", "variation_runs", ["status"])
    op.create_index("ix_variation_runs_created_at", "variation_runs", ["created_at"])

    op.create_table(
        "review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=False),
        sa.Column("next_status", sa.String(20), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_events_question_id", "review_events", ["question_id"])
    op.create_index("ix_review_events_created_at", "review_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("review_events")
    op.drop_table("variation_runs")
    op.drop_table("question_learning")
