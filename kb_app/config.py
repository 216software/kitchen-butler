import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "kitchen-butler"
CONFIG_PATH = CONFIG_DIR / "config.json"


def get_default_user() -> str | None:
    env_user = os.environ.get("KB_USER")
    if env_user:
        return env_user
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())
        return data.get("default_user")
    return None


def set_default_user(username: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())
    data["default_user"] = username
    CONFIG_PATH.write_text(json.dumps(data, indent=2))
