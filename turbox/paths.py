"""Central project paths.

All paths are resolved from the TurBox project directory, not from the current
working directory. This makes direct Python launches and .bat launches behave
consistently.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
DEBUG_DIR = PROJECT_ROOT / "debug_logs"
POSTS_DIR = PROJECT_ROOT / "posts"
POSTS_COLLECTIONS_DIR = PROJECT_ROOT / "postsCollections"
SAMPLES_DIR = PROJECT_ROOT / "samples"
