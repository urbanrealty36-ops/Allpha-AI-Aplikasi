"""Make sibling helper modules (e.g. knowledge_worker_fakes) importable on any runner."""
import sys
from pathlib import Path

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)
