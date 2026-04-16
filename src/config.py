import ast
import os
import json


def load_env_file(path: str = ".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)


load_env_file()

BOT_TOKEN = os.environ.get("AMEVA_BOT_TOKEN")
MY_CHAT_ID = int(os.environ.get("AMEVA_MY_CHAT_ID", "0"))

project_map_value = os.environ.get("PROJECT_MAP", "{}")
if isinstance(project_map_value, str):
    try:
        project_map_value = ast.literal_eval(project_map_value)
    except Exception:
        project_map_value = {}

PROJECT_MAP = {
    str(k).lower(): v
    for k, v in (project_map_value.items() if isinstance(project_map_value, dict) else {})
}

if not BOT_TOKEN:
    raise SystemExit("환경 변수 AMEVA_BOT_TOKEN을 설정하세요.")

DEFAULT_GIT_PATH = os.environ.get("DEFAULT_GIT_PATH", os.path.join(os.getcwd(), "git_repos"))
PROJECTS_FILE = os.path.join(os.getcwd(), "projects.json")
CMD_LOG_FILE = os.path.join(os.getcwd(), "cmd.log")
GIT_LOG_FILE = os.path.join(os.getcwd(), "git.log")
CMD_SAFE_MODE = os.environ.get("CMD_SAFE_MODE", "false").lower() in ("1", "true", "yes", "on")

# 기본값들
current_target = "오케스트라"
PROJECT_PATHS = {
    "AMEVA": r"C:\ameva\AMEVA-Doc-AI",
    "오케스트라": r"C:\ameva\Orchestra",
    "벤치마크": r"C:\ameva\Benchmark"
}

# In-memory registry (populated from projects.json)
PROJECT_AMP = {}
PENDING_GIT_ACTIONS = {}
