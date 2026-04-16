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

def get_env_as_dict(key: str, default: str = "{}") -> dict:
    val = os.environ.get(key, default)
    try:
        # dict 형태의 문자열을 안전하게 파싱 후 key를 소문자로 변환
        parsed = ast.literal_eval(val)
        return {str(k).lower(): v for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (ValueError, SyntaxError):
        return {}
    
load_env_file()

# 기본값들
BOT_TOKEN = os.environ.get("AMEVA_BOT_TOKEN")
MY_CHAT_ID = int(os.environ.get("AMEVA_MY_CHAT_ID", "0"))

current_target = "오케스트라"
PROJECT_MAP = get_env_as_dict("PROJECT_MAP")
PROJECT_PATHS = get_env_as_dict("PROJECT_PATHS")

if not BOT_TOKEN:
    raise SystemExit("환경 변수 AMEVA_BOT_TOKEN을 설정하세요.")

DEFAULT_GIT_PATH = os.environ.get("DEFAULT_GIT_PATH", os.path.join(os.getcwd(), "git_repos"))
PROJECTS_FILE = os.path.join(os.getcwd(), "projects.json")
CMD_LOG_FILE = os.path.join(os.getcwd(), "cmd.log")
GIT_LOG_FILE = os.path.join(os.getcwd(), "git.log")
CMD_SAFE_MODE = os.environ.get("CMD_SAFE_MODE", "false").lower() in ("1", "true", "yes", "on")

# In-memory registry (populated from projects.json)
PROJECT_AMP = {}
PENDING_GIT_ACTIONS = {}
