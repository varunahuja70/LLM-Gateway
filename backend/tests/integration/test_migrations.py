import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_alembic_upgrade_and_downgrade() -> None:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.exists()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_migration.db"
        sqlite_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)
        alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))

        # Run upgrade to head
        command.upgrade(alembic_cfg, "head")
        assert db_file.exists()

        # Run downgrade to base
        command.downgrade(alembic_cfg, "base")

        # Run upgrade back to head to verify idempotent re-upgrade
        command.upgrade(alembic_cfg, "head")
