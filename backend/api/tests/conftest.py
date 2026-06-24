import os
import sys
from pathlib import Path

BACKEND_API_ROOT = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_API_ROOT / "tests" / ".test_auth.sqlite3"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB_PATH}")
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key")

if str(BACKEND_API_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_ROOT))
