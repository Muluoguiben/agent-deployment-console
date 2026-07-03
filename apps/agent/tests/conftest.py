import sqlite3
from pathlib import Path

import pytest

from agent_service import db, registry

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    connection = db.connect(tmp_path / "test.db")
    db.init_db(connection)
    registry.ensure_seed_version(connection)
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR
