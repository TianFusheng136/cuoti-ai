"""建立题目录入、识别、模型配置和分析基础表。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("capability", sa.String(16), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("secret_ref", sa.String(255), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_test_status", sa.String(32)),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_configs_capability", "provider_configs", ["capability"])

    op.create_table(
        "questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("input_type", sa.String(16), nullable=False),
        sa.Column("source_text", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_status", "questions", ["status"])
    op.create_index("ix_questions_created_at", "questions", ["created_at"])

    op.create_table(
        "question_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_assets_question_id", "question_assets", ["question_id"])

    op.create_table(
        "recognition_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_config_id",
            sa.String(36),
            sa.ForeignKey("provider_configs.id", ondelete="SET NULL"),
        ),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("recognized_text", sa.Text()),
        sa.Column("question_completeness", sa.String(16)),
        sa.Column("confidence", sa.String(16)),
        sa.Column("output_json", sa.JSON()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_recognition_runs_question_id", "recognition_runs", ["question_id"])
    op.create_index("ix_recognition_runs_status", "recognition_runs", ["status"])
    op.create_index("ix_recognition_runs_created_at", "recognition_runs", ["created_at"])

    op.create_table(
        "question_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("recognized_text_snapshot", sa.Text()),
        sa.Column("confirmed_text", sa.Text(), nullable=False),
        sa.Column("confirmed_text_hash", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(100)),
        sa.Column("grade", sa.String(100)),
        sa.Column("user_answer", sa.Text()),
        sa.Column("user_solution", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_question_confirmations_question_id", "question_confirmations", ["question_id"]
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(36),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "confirmation_id",
            sa.String(36),
            sa.ForeignKey("question_confirmations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_config_id",
            sa.String(36),
            sa.ForeignKey("provider_configs.id", ondelete="SET NULL"),
        ),
        sa.Column("confirmed_text_snapshot", sa.Text(), nullable=False),
        sa.Column("confirmed_text_hash", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("normalized_question", sa.Text()),
        sa.Column("question_completeness", sa.String(16)),
        sa.Column("confidence", sa.String(16)),
        sa.Column("output_json", sa.JSON()),
        sa.Column("verification_json", sa.JSON()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error_code", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analysis_runs_question_id", "analysis_runs", ["question_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_index("ix_analysis_runs_created_at", "analysis_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("analysis_runs")
    op.drop_table("question_confirmations")
    op.drop_table("recognition_runs")
    op.drop_table("question_assets")
    op.drop_table("questions")
    op.drop_table("provider_configs")
