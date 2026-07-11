import os
import shutil
import sys
import tempfile
from pathlib import Path

_tmp_dir = Path(tempfile.mkdtemp(prefix="pirapire_test_"))
_tmp_db = _tmp_dir / "pirapire_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["INTEGRATION_MASTER_KEY_PATH"] = str(_tmp_dir / "integration-master.key")
os.environ["CONFIG_ADMIN_PASSWORD_PATH"] = str(_tmp_dir / "config-admin.password")
os.environ["CONFIG_SESSION_KEY_PATH"] = str(_tmp_dir / "config-session.key")
os.environ["FOOTBALL_SYNC_UI_BOOTSTRAP_REQUIRED"] = "false"

_app_dir = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(_app_dir.parent))

import atexit


def _cleanup():
    try:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(_tmp_db) + suffix)
            if p.exists():
                p.unlink()
    finally:
        if _tmp_dir.exists():
            shutil.rmtree(_tmp_dir, ignore_errors=True)


atexit.register(_cleanup)

from app.database import init_db  # noqa: E402

init_db()
