"""pytest 共享配置。

把 backend/ 加入 sys.path，让 tests/ 可以 import app.*。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
