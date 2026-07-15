import os
import sys
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "pirapire_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"

_app_dir = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(_app_dir.parent))

if _tmp_db.exists():
    _tmp_db.unlink()

from app.database import init_db  # noqa: E402

init_db()
