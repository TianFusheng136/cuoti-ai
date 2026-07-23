from alembic import context

from backend.app.db import models as database_models  # noqa: F401
from backend.app.db.base import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("数据库迁移必须由应用通过现有连接执行。")

context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    compare_type=True,
    render_as_batch=True,
)

with context.begin_transaction():
    context.run_migrations()
