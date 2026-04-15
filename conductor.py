import ast
import os
import re
import telebot
import telebot.apihelper as apihelper
import pyautogui
import pygetwindow as gw
import pyperclip
import time
import subprocess
import io
from PIL import ImageGrab

# --- [설정 영역] ---

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

# 본인의 텔레그램 ID (숫자) - MY_CHAT_ID를 0으로 두면 모든 채팅에서 동작합니다.
if not BOT_TOKEN:
    raise SystemExit("환경 변수 AMEVA_BOT_TOKEN을 설정하세요.")

DEFAULT_GIT_PATH = os.environ.get("DEFAULT_GIT_PATH", os.path.join(os.getcwd(), "git_repos"))
PROJECT_AMP = {}
PENDING_GIT_ACTIONS = {}

# 실제 VS Code에서 프로젝트 창 제목에 포함되는 키워드를 적습니다.
current_target = "오케스트라"  # 처음 기본으로 열어둘 프로젝트명

# 필요시 본인 환경에 맞게 실제 폴더 경로를 설정하세요.
PROJECT_PATHS = {
    "AMEVA": r"C:\ameva\AMEVA-Doc-AI",
    "오케스트라": r"C:\ameva\Orchestra",
    "벤치마크": r"C:\ameva\Benchmark"
}

bot = telebot.TeleBot(BOT_TOKEN)
apihelper.CONNECT_TIMEOUT = 10
apihelper.READ_TIMEOUT = 15
print("🚀 AMEVA-Conductor 시작됨. 지휘를 시작하세요!")

# --- [유틸 함수] ---
def open_project_in_vscode(project_name: str) -> bool:
    path = PROJECT_PATHS.get(project_name)
    if not path or not os.path.exists(path):
        return False
    try:
        subprocess.run(f'code "{path}"', shell=True)
        return True
    except Exception:
        return False


def find_vscode_window(keyword: str):
    all_windows = gw.getAllWindows()
    for w in all_windows:
        if keyword in w.title and 'Visual Studio Code' in w.title:
            return w
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
    if key not in PROJECT_AMP:
        return key

    indexes = [1] * len(parts)
    while True:
        candidate = ''.join(
            (parts[i][indexes[i]].upper() if indexes[i] < len(parts[i]) else parts[i][-1].upper())
            for i in range(len(parts))
        )
        if candidate not in PROJECT_AMP:
            return candidate
        for i in range(len(indexes)):
            if indexes[i] < len(parts[i]) - 1:
                indexes[i] += 1
                break
        else:
            candidate = f"{key}{len(PROJECT_AMP) + 1}"
            if candidate not in PROJECT_AMP:
                return candidate


def save_project_amp(repo_url: str, repo_name: str, repo_path: str) -> str:
    key = generate_project_key(repo_name)
    PROJECT_AMP[key] = {
        "url": repo_url,
        "name": repo_name,
        "path": repo_path
    }
    return key


def run_shell(command: str, cwd: str | None = None) -> tuple[str, str, int]:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='cp949', cwd=cwd)
    return result.stdout or "", result.stderr or "", result.returncode


def run_git_clone(git_url: str, dest_parent: str) -> tuple[bool, str, str, str]:
    repo_name = get_repo_name_from_url(git_url)
    if os.path.basename(dest_parent).lower() == repo_name.lower():
        clone_target = dest_parent
    elif os.path.isdir(dest_parent):
        clone_target = os.path.join(dest_parent, repo_name)
    else:
        clone_target = dest_parent

    os.makedirs(os.path.dirname(clone_target), exist_ok=True)
    stdout, stderr, returncode = run_shell(f'git clone "{git_url}" "{clone_target}"', cwd=os.path.dirname(clone_target))
    return (returncode == 0, stdout, stderr, clone_target)


# --- [기능 1: 스크린샷 모니터링] ---
@bot.message_handler(commands=['see', '화면'])
def send_screenshot(message):
    try:
        screenshot = ImageGrab.grab()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        bot.send_photo(message.chat.id, img_byte_arr, caption=f"현재 화면 (Target: {current_target})")
    except Exception as e:
        bot.reply_to(message, f"❌ 캡처 실패: {e}")


# --- [기능 2: 실행 취소] ---
@bot.message_handler(commands=['undo', 'z'])
def undo_action(message):
    try:
        win = gw.getWindowsWithTitle(current_target)[0]
        win.activate()
        pyautogui.hotkey('ctrl', 'z')
        bot.reply_to(message, "⏪ 실행 취소 완료")
    except Exception:
        bot.reply_to(message, "❌ 창을 찾을 수 없습니다.")


# --- [기능 3: 관리자/시스템 명령어] ---
@bot.message_handler(func=lambda m: m.text and m.text.startswith('!cmd'))
def run_cmd(message):
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return
    cmd = message.text.replace('!cmd', '').strip()
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp949')
        output = result.stdout if result.stdout else result.stderr
        if not output:
            bot.reply_to(message, "✅ 명령이 실행되었지만 출력이 없습니다.")
            return

        max_len = 4000
        for i in range(0, len(output), max_len):
            chunk = output[i:i + max_len]
            bot.reply_to(message, f"{chunk}")
    except Exception as e:
        bot.reply_to(message, f"❌ 명령 실행 실패: {e}")


@bot.message_handler(func=lambda m: m.text is not None and m.chat.id in PENDING_GIT_ACTIONS)
def pending_git_handler(message):
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return

    pending = PENDING_GIT_ACTIONS.get(message.chat.id)
    text = message.text.strip()
    if not pending:
        return

    if pending.get('type') == 'git_clone':
        url = extract_git_url(text)
        if url:
            path = pending.get('path') or DEFAULT_GIT_PATH
            success, stdout, stderr, clone_target = run_git_clone(url, path)
            del PENDING_GIT_ACTIONS[message.chat.id]
            if success:
                project_key = save_project_amp(url, get_repo_name_from_url(url), clone_target)
                bot.reply_to(message, f"✅ git clone 완료: {clone_target}\n프로젝트 등록: {project_key}")
            else:
                bot.reply_to(message, f"❌ git clone 실패:\n{stderr or stdout}")
            return

        if pending.get('state') == 'confirm_default' and is_yes_reply(text):
            pending['path'] = DEFAULT_GIT_PATH
            pending['state'] = 'await_url'
            bot.reply_to(message, f"✅ 기본 경로로 저장합니다: {DEFAULT_GIT_PATH}\n이제 클론할 깃 URL을 보내주세요.")
            return

        bot.reply_to(message, "❌ 깃 주소를 찾지 못했습니다. URL을 보내거나 'ㅇㅇ'으로 기본 경로를 지정해 주세요.")
        return


@bot.message_handler(func=lambda m: m.text and m.text.startswith('!git'))
def git_handler(message):
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return

    command_text = message.text[4:].strip()
    if not command_text:
        bot.reply_to(message, "❗ git 명령어를 입력하세요. 예: !git clone <url>")
        return

    if command_text.startswith('clone'):
        url = extract_git_url(command_text)
        path = extract_local_path(command_text)
        if url:
            if not path:
                path = DEFAULT_GIT_PATH
            success, stdout, stderr, clone_target = run_git_clone(url, path)
            if success:
                project_key = save_project_amp(url, get_repo_name_from_url(url), clone_target)
                bot.reply_to(message, f"✅ git clone 완료: {clone_target}\n프로젝트 등록: {project_key}")
            else:
                bot.reply_to(message, f"❌ git clone 실패:\n{stderr or stdout}")
            return

        if path:
            PENDING_GIT_ACTIONS[message.chat.id] = {"type": "git_clone", "path": path, "state": "await_url"}
            bot.reply_to(message, f"✅ 경로를 확인했습니다: {path}\n이제 클론할 깃 URL을 보내주세요.")
            return

        PENDING_GIT_ACTIONS[message.chat.id] = {"type": "git_clone", "state": "confirm_default"}
        bot.reply_to(message, "깃 URL이 없습니다. 기본 주소로 저장할까요? 응답으로 'ㅇㅇ' 이나 '응'을 보내주세요.")
        return

    cwd = extract_local_path(command_text) or DEFAULT_GIT_PATH
    if not os.path.exists(cwd):
        bot.reply_to(message, f"❌ 경로를 찾을 수 없습니다: {cwd}")
        return

    stdout, stderr, returncode = run_shell(f'git {command_text}', cwd=cwd)
    output = stdout if stdout else stderr
    if not output:
        bot.reply_to(message, "✅ git 명령 실행 완료: 출력이 없습니다.")
        return

    max_len = 4000
    for i in range(0, len(output), max_len):
        bot.reply_to(message, output[i:i + max_len])
    return


@bot.message_handler(func=lambda m: m.text and m.text.startswith('!projects'))
def list_projects(message):
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return

    lines = ["📁 PROJECT_MAP:"]
    for tag, target in PROJECT_MAP.items():
        lines.append(f"{tag} -> {target}")
    lines.append("\n🧩 PROJECT_AMP:")
    if PROJECT_AMP:
        for key, data in PROJECT_AMP.items():
            lines.append(f"{key} -> name: {data['name']}, url: {data['url']}, path: {data['path']}")
    else:
        lines.append("(등록된 git 프로젝트가 없습니다.)")

    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(func=lambda m: m.text and m.text.startswith('!ai'))
def ai_handler(message):
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return
    bot.reply_to(message, "🤖 !ai 기능은 준비 중입니다. 곧 사용할 수 있습니다.")


# --- [기능 4: 프로젝트 태그 기반 VS Code 제어] ---
@bot.message_handler(func=lambda message: message.text is not None)
def handle_message(message):
    global current_target
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return

    text = message.text.strip()
    if not text:
        return

    text_lower = text.lower()
    tag_found = False
    for tag, keyword in PROJECT_MAP.items():
        if text_lower.startswith(tag):
            current_target = keyword
            text = text[len(tag):].strip()
            tag_found = True
            break

    if tag_found and not text:
        bot.reply_to(message, f"🔄 타겟 변경: 이제부터 [{current_target}] 창으로 명령을 보냅니다.")
        return

    try:
        win = find_vscode_window(current_target)
        if not win:
            opened = open_project_in_vscode(current_target)
            if opened:
                time.sleep(2)
                win = find_vscode_window(current_target)

        if not win:
            bot.reply_to(message, f"❌ '{current_target}' 창을 찾을 수 없습니다.")
            return

        win.activate()
        time.sleep(0.5)

        pyautogui.hotkey('ctrl', 'shift', 'l')
        time.sleep(0.2)

        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press('enter')

        bot.reply_to(message, f"✅ [{current_target}] 전송 완료!")
    except Exception as e:
        bot.reply_to(message, f"❌ 에러 발생: {e}")


try:
    bot.polling(non_stop=True, interval=0, timeout=10, long_polling_timeout=20)
except KeyboardInterrupt:
    print("봇이 수동으로 중지되었습니다.")
except Exception as e:
    print(f"봇 실행 중 오류: {e}")
        
        