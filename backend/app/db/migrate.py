"""Apply Alembic migrations to the configured database."""

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR


def upgrade_database() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", (BACKEND_DIR / "migrations").as_posix())
    command.upgrade(config, "head")
