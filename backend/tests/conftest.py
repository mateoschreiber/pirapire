import os
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "pirapire_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
