"""ATRI - 亚托莉, a role-playing AI chatbot powered by DeepSeek."""
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    RESOURCE_DIR = Path(sys._MEIPASS)
    BASE_DIR = _EXE_DIR
    SKILLS_DIR = _EXE_DIR / "skills"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    RESOURCE_DIR = BASE_DIR
    SKILLS_DIR = BASE_DIR / "skills"

DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "workspace"
