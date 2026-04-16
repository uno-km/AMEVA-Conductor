import os
import re
import subprocess
import json
from datetime import datetime
from typing import Tuple
 

from . import config


def open_project_in_vscode(project_name: str) -> bool:
    path = config.PROJECT_PATHS.get(project_name)
    if not path or not os.path.exists(path):
        return False
    try:
        subprocess.run(f'code "{path}"', shell=True)
        return True
    except Exception:
        return False


def find_vscode_window(keyword: str):
    try:
        import pygetwindow as gw
    except Exception:
        return None
    try:
        all_windows = gw.getAllWindows()
        for w in all_windows:
            if keyword in w.title and 'Visual Studio Code' in w.title:
                return w
    except Exception:
        return None
    return None


def is_yes_reply(text: str) -> bool:
    if not text:
        return False
    normalized = text.strip().lower()
    yes_tokens = ["ㅇㅇ", "응", "ㅇㅇㅇ", "ㅇㅇㅇㅇ", "ㅇ", "네", "yes", "ok", "y"]
    return any(token in normalized for token in yes_tokens)


def extract_git_url(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    patterns = [
        r'(git@[^\s]+:\S+?\.git)',
        r'(https?://[^\s]+?\.git)',
        r'(https?://[^\s]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group(1).strip().rstrip('.,')
            return url
    return None


def extract_local_path(text: str) -> str | None:
    if not text:
        return None
    tokens = re.split(r'\s+', text)
    for token in tokens:
        token = token.strip('"\'"').rstrip(',')
        if not token:
            continue
        if extract_git_url(token):
            continue
        if '\\' in token or re.match(r'^[A-Za-z]:[\\/]', token) or token.startswith('/'):
            return token
    return None


def get_repo_name_from_url(url: str) -> str:
    repo_name = url.rstrip('/').split('/')[-1]
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    return repo_name


def generate_project_key(repo_name: str) -> str:
    parts = [part for part in re.split(r'[-_]', repo_name) if part]
    if not parts:
        parts = [repo_name]
    key = ''.join(part[0].upper() for part in parts)
    if key not in config.PROJECT_AMP:
        return key

    indexes = [1] * len(parts)
    while True:
        candidate = ''.join(
            (parts[i][indexes[i]].upper() if indexes[i] < len(parts[i]) else parts[i][-1].upper())
            for i in range(len(parts))
        )
        if candidate not in config.PROJECT_AMP:
            return candidate
        for i in range(len(indexes)):
            if indexes[i] < len(parts[i]) - 1:
                indexes[i] += 1
                break
        else:
            candidate = f"{key}{len(config.PROJECT_AMP) + 1}"
            if candidate not in config.PROJECT_AMP:
                return candidate


def save_project_amp(repo_url: str, repo_name: str, repo_path: str) -> str:
    key = generate_project_key(repo_name)
    config.PROJECT_AMP[key] = {
        "url": repo_url,
        "name": repo_name,
        "path": repo_path
    }
    try:
        save_projects()
    except Exception:
        pass
    append_git_log(f"Registered project {key}: {repo_name} -> {repo_path}")
    return key


def run_shell(command: str, cwd: str | None = None) -> Tuple[str, str, int]:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='cp949', cwd=cwd)
    return result.stdout or "", result.stderr or "", result.returncode


def run_git_clone(git_url: str, dest_parent: str) -> Tuple[bool, str, str, str]:
    repo_name = get_repo_name_from_url(git_url)
    if os.path.basename(dest_parent).lower() == repo_name.lower():
        clone_target = dest_parent
    elif os.path.isdir(dest_parent):
        clone_target = os.path.join(dest_parent, repo_name)
    else:
        clone_target = dest_parent

    os.makedirs(os.path.dirname(clone_target), exist_ok=True)
    append_git_log(f"Attempting git clone: {git_url} -> {clone_target}")
    stdout, stderr, returncode = run_shell(f'git clone "{git_url}" "{clone_target}"', cwd=os.path.dirname(clone_target))
    append_git_log(f"git clone result: url={git_url} target={clone_target} rc={returncode} stdout={stdout[:1000]} stderr={stderr[:1000]}")
    return (returncode == 0, stdout, stderr, clone_target)


def append_cmd_log(entry: str):
    try:
        with open(config.CMD_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {entry}\n")
    except Exception:
        pass


def append_git_log(entry: str):
    try:
        with open(config.GIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {entry}\n")
    except Exception:
        pass


def load_projects():
    try:
        if os.path.exists(config.PROJECTS_FILE):
            with open(config.PROJECTS_FILE, encoding='utf-8') as f:
                data = json.load(f)
                config.PROJECT_AMP.clear()
                config.PROJECT_AMP.update(data)
        else:
            config.PROJECT_AMP.clear()
    except Exception as e:
        append_git_log(f"Failed to load projects.json: {e}")
        config.PROJECT_AMP.clear()


def save_projects():
    try:
        with open(config.PROJECTS_FILE, "w", encoding='utf-8') as f:
            json.dump(config.PROJECT_AMP, f, indent=2, ensure_ascii=False)
    except Exception as e:
        append_git_log(f"Failed to save projects.json: {e}")


def is_command_safe(cmd: str) -> bool:
    if not config.CMD_SAFE_MODE:
        return True
    banned = [
        r"\\brm\\s+-rf\\b",
        r"\\brm\\s+-r\\b",
        r"\\bshutdown\\b",
        r"\\breboot\\b",
        r"\\bpoweroff\\b",
        r"\\bformat\\b",
        r"\\bmkfs\\b",
        r"\\bsc\\s+delete\\b",
        r"\\bcipher\\s+\\/w\\b",
        r"\\brmdir\\s+\\/s\\b",
    ]
    for p in banned:
        if re.search(p, cmd, flags=re.I):
            return False
    return True
