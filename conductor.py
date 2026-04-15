import os
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
# 본인의 텔레그램 ID (숫자) - MY_CHAT_ID를 0으로 두면 모든 채팅에서 동작합니다.
if not BOT_TOKEN:
    raise SystemExit("환경 변수 AMEVA_BOT_TOKEN을 설정하세요.")
PROJECT_MAP = {
    "#doc": "AMEVA",
    "#orc": "오케스트라",
    "#bench": "벤치마크"
}
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


# --- [기능 4: 프로젝트 태그 기반 VS Code 제어] ---
@bot.message_handler(func=lambda message: message.text is not None)
def handle_message(message):
    global current_target
    if MY_CHAT_ID != 0 and message.chat.id != MY_CHAT_ID:
        return

    text = message.text.strip()
    if not text:
        return

    tag_found = False
    for tag, keyword in PROJECT_MAP.items():
        if text.startswith(tag):
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
        
        