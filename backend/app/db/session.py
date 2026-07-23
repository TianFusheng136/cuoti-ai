from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_engine(database_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def initialize_database(engine: Engine) -> None:
    migration_root = Path(__file__).resolve().parent / "migrations"
    config = Config()
    config.set_main_option("script_location", migration_root.as_posix())

    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        config.attributes["connection"] = connection
        if "questions" in tables and "alembic_version" not in tables:
            learning_tables = {"question_learning", "variation_runs", "review_events"}
            baseline = "0002" if learning_tables <= tables else "0001"
            command.stamp(config, baseline)
        command.upgrade(config, "head")


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
