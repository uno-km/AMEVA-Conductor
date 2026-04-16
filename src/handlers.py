from email.mime import message
import time
import io
import telebot
from telebot import types

from . import config
from . import utils


MAX_CHAT_LEN = 4000



def register_handlers(bot: telebot.TeleBot):
    
    
    def reply_long(bot, message, text):
        if not text:
            bot.reply_to(message, "✅ 실행 완료 (출력 없음)")
            return
        for i in range(0, len(text), MAX_CHAT_LEN):
            bot.reply_to(message, text[i:i + MAX_CHAT_LEN])

    def require_owner(handler):
        def wrapper(message):
            if config.MY_CHAT_ID != 0 and message.chat.id != config.MY_CHAT_ID:
                return
            return handler(message)
        return wrapper


    @bot.message_handler(commands=['see', '화면'])
    def send_screenshot(message):
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            bot.send_photo(message.chat.id, img_byte_arr, caption=f"현재 화면 (Target: {config.current_target})")
        except Exception as e:
            bot.reply_to(message, f"❌ 캡처 실패: {e}")

    @bot.message_handler(commands=['undo', 'z'])
    def undo_action(message):
        try:
            import pygetwindow as gw
            import pyautogui
            win = gw.getWindowsWithTitle(config.current_target)[0]
            win.activate()
            pyautogui.hotkey('ctrl', 'z')
            bot.reply_to(message, "⏪ 실행 취소 완료")
        except Exception:
            bot.reply_to(message, "❌ 창을 찾을 수 없습니다.")

    @bot.message_handler(func=lambda m: m.text and m.text.startswith('!cmd'))
    @require_owner
    def run_cmd(message):
        cmd = message.text.replace('!cmd', '').strip()
        if not cmd:
            bot.reply_to(message, "❗ 명령어가 비어 있습니다.")
            return
        if not utils.is_command_safe(cmd):
            bot.reply_to(message, "❌ 해당 명령은 안전 모드에서 차단되었습니다.")
            try:
                utils.append_cmd_log(f"user:{message.from_user.id} blocked: {cmd}")
            except Exception:
                pass
            return
        try:
            stdout, stderr, returncode = utils.run_shell(cmd)
            output = stdout if stdout else stderr
            try:
                utils.append_cmd_log(f"user:{message.from_user.id} cmd:{cmd} rc:{returncode} out:{(output or '')[:1000].replace(chr(10),' ')}")
            except Exception:
                pass
            if not output:
                bot.reply_to(message, "✅ 명령이 실행되었지만 출력이 없습니다.")
                return
            
            reply_long(bot, message, output)

        except Exception as e:
            try:
                utils.append_cmd_log(f"user:{message.from_user.id} cmd:{cmd} error:{e}")
            except Exception:
                pass
            bot.reply_to(message, f"❌ 명령 실행 실패: {e}")

    @bot.message_handler(func=lambda m: m.text is not None and m.chat.id in config.PENDING_GIT_ACTIONS)
    @require_owner
    def pending_git_handler(message):
        pending = config.PENDING_GIT_ACTIONS.get(message.chat.id)
        text = message.text.strip()
        if not pending:
            return
        if pending.get('type') == 'git_clone':
            url = utils.extract_git_url(text)
            if url:
                path = pending.get('path') or config.DEFAULT_GIT_PATH
                try:
                    utils.append_git_log(f"User {message.from_user.id} confirmed clone: {url} -> {path}")
                except Exception:
                    pass
                success, stdout, stderr, clone_target = utils.run_git_clone(url, path)
                del config.PENDING_GIT_ACTIONS[message.chat.id]
                if success:
                    project_key = utils.save_project_amp(url, utils.get_repo_name_from_url(url), clone_target)
                    bot.reply_to(message, f"✅ git clone 완료: {clone_target}\n프로젝트 등록: {project_key}")
                else:
                    try:
                        utils.append_git_log(f"git clone failed for user {message.from_user.id}: url={url} err={stderr or stdout}")
                    except Exception:
                        pass
                    bot.reply_to(message, f"❌ git clone 실패:\n{stderr or stdout}")
                return
            if pending.get('state') == 'confirm_default' and utils.is_yes_reply(text):
                pending['path'] = config.DEFAULT_GIT_PATH
                pending['state'] = 'await_url'
                bot.reply_to(message, f"✅ 기본 경로로 저장합니다: {config.DEFAULT_GIT_PATH}\n이제 클론할 깃 URL을 보내주세요.")
                return
            bot.reply_to(message, "❌ 깃 주소를 찾지 못했습니다. URL을 보내거나 'ㅇㅇ'으로 기본 경로를 지정해 주세요.")
            return

    @bot.message_handler(func=lambda m: m.text and m.text.startswith('!git'))
    @require_owner
    def git_handler(message):
        command_text = message.text[4:].strip()
        if not command_text:
            bot.reply_to(message, "❗ git 명령어를 입력하세요. 예: !git clone <url>")
            return
        if command_text.startswith('clone'):
            url = utils.extract_git_url(command_text)
            path = utils.extract_local_path(command_text)
            if url:
                if not path:
                    path = config.DEFAULT_GIT_PATH
                try:
                    utils.append_git_log(f"User {message.from_user.id} requested clone: {url} -> {path}")
                except Exception:
                    pass
                success, stdout, stderr, clone_target = utils.run_git_clone(url, path)
                if success:
                    project_key = utils.save_project_amp(url, utils.get_repo_name_from_url(url), clone_target)
                    bot.reply_to(message, f"✅ git clone 완료: {clone_target}\n프로젝트 등록: {project_key}")
                else:
                    try:
                        utils.append_git_log(f"git clone failed for user {message.from_user.id}: url={url} err={stderr or stdout}")
                    except Exception:
                        pass
                    bot.reply_to(message, f"❌ git clone 실패:\n{stderr or stdout}")
                return
            if path:
                config.PENDING_GIT_ACTIONS[message.chat.id] = {"type": "git_clone", "path": path, "state": "await_url"}
                bot.reply_to(message, f"✅ 경로를 확인했습니다: {path}\n이제 클론할 깃 URL을 보내주세요.")
                return
            config.PENDING_GIT_ACTIONS[message.chat.id] = {"type": "git_clone", "state": "confirm_default"}
            bot.reply_to(message, "깃 URL이 없습니다. 기본 주소로 저장할까요? 응답으로 'ㅇㅇ' 이나 '응'을 보내주세요.")
            return
        cwd = utils.extract_local_path(command_text) or config.DEFAULT_GIT_PATH
        if not os.path.exists(cwd):
            bot.reply_to(message, f"❌ 경로를 찾을 수 없습니다: {cwd}")
            return
        stdout, stderr, returncode = utils.run_shell(f'git {command_text}', cwd=cwd)
        output = stdout if stdout else stderr
        if not output:
            bot.reply_to(message, "✅ git 명령 실행 완료: 출력이 없습니다.")
            return       
        reply_long(bot, message, output)


    @bot.message_handler(func=lambda m: m.text and m.text.startswith('!projects'))
    @require_owner
    def list_projects(message):
        lines = ["📁 PROJECT_MAP:"]
        for tag, target in config.PROJECT_MAP.items():
            lines.append(f"{tag} -> {target}")
        lines.append("\n🧩 PROJECT_AMP:")
        if config.PROJECT_AMP:
            for key, data in config.PROJECT_AMP.items():
                lines.append(f"{key} -> name: {data['name']}, url: {data['url']}, path: {data['path']}")
        else:
            lines.append("(등록된 git 프로젝트가 없습니다.)")
        bot.reply_to(message, "\n".join(lines))

    @bot.message_handler(func=lambda m: m.text and m.text.startswith('!ai'))
    @require_owner
    def ai_handler(message):
        bot.reply_to(message, "🤖 !ai 기능은 준비 중입니다. 곧 사용할 수 있습니다.")

    @bot.message_handler(func=lambda message: message.text is not None)
    @require_owner
    def handle_message(message):
        text = message.text.strip()
        if not text:
            return
        text_lower = text.lower()
        tag_found = False
        for tag, keyword in config.PROJECT_MAP.items():
            if text_lower.startswith(tag):
                config.current_target = keyword
                text = text[len(tag):].strip()
                tag_found = True
                break
        if tag_found and not text:
            focus_target_window(bot, message, config.current_target)
            bot.reply_to(message, f"🔄 타겟 변경: 이제부터 [{config.current_target}] 창으로 명령을 보냅니다.")
            return
        try:
            import pyautogui
            import pyperclip
            win = utils.find_vscode_window(config.current_target)
            if not win:
                opened = utils.open_project_in_vscode(config.current_target)
                if opened:
                    time.sleep(2)
                    win = utils.find_vscode_window(config.current_target)
            if not win:
                bot.reply_to(message, f"❌ '{config.current_target}' 창을 찾을 수 없습니다.")
                return
            win.activate()
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'shift', 'I')
            time.sleep(0.2)
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyautogui.press('enter')
            bot.reply_to(message, f"✅ [{config.current_target}] 전송 완료!")
        except Exception as e:
            bot.reply_to(message, f"❌ 에러 발생: {e}")
            
    def focus_target_window(bot, message, target_name):
        """지정한 타겟 창을 찾아 활성화하고 사용자에게 알림을 보냅니다."""
        try:
            import pygetwindow as gw
            import time

            # 1. VS Code 창 찾기 (기존 utils 활용)
            win = utils.find_vscode_window(target_name)
            
            # 2. 창이 없으면 열기 시도
            if not win:
                bot.send_chat_action(message.chat.id, 'typing')
                opened = utils.open_project_in_vscode(target_name)
                if opened:
                    time.sleep(3)  # 창이 뜨는 시간 대기
                    win = utils.find_vscode_window(target_name)

            # 3. 창이 존재하면 활성화(화면에 띄우기)
            if win:
                if win.isMinimized:
                    win.restore()
                win.activate()
                bot.reply_to(message, f"🎯 타겟 변경 및 활성화: [{target_name}]\n이제 이 창이 화면 제일 앞에 있습니다.")
                return True
            else:
                bot.reply_to(message, f"🔄 타겟은 [{target_name}](으)로 변경됐지만, 창을 찾거나 실행할 수 없습니다.")
                return False
            
        except Exception as e:
                bot.reply_to(message, f"❌ 창 활성화 중 에러: {e}")
                return False
            
    

        # 1. 확인/취소 버튼을 띄우는 함수
    def ask_confirm(bot, message, action_type, detail):
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # callback_data에 어떤 동작인지와 승인 여부를 담습니다.
        btn_yes = types.InlineKeyboardButton("✅ 확인", callback_data=f"{action_type}_yes_{detail}")
        btn_no = types.InlineKeyboardButton("❌ 취소", callback_data=f"{action_type}_no")
        
        markup.add(btn_yes, btn_no)
        
        bot.send_message(message.chat.id, f"❓ [{detail}] 작업을 실행할까요?", reply_markup=markup)

        
    @bot.message_handler(func=lambda m: m.text and m.text.startswith('!test'))
    @require_owner
    def run_cmd_with_confirm(message):
        # 바로 실행하지 않고 버튼을 먼저 보냅니다.
        markup = types.InlineKeyboardMarkup()
        # 주의: callback_data는 64바이트 제한이 있으므로 명령어가 너무 길면 별도 관리가 필요합니다.
        markup.add(
            types.InlineKeyboardButton("실행", callback_data=f"test_y"), 
            types.InlineKeyboardButton("취소", callback_data="test_n")
        )
        bot.reply_to(message, f"⚠️ 다음 명령을 실행할까요?", parse_mode="Markdown", reply_markup=markup)
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith('test_'))
    def handle_test_callback(call):
        if call.data == "test_yes":
            # (A) 기존 메시지를 수정해서 "실행 중" 표시 (UI 피드백)
            bot.edit_message_text("✅ 실행이 눌렸습니다~ 서버에서 작업을 시작합니다!", 
                                call.message.chat.id, 
                                call.message.message_id)
            
            # (B) 서버 터미널(로그)에 출력
            print(f">>> [SERVER LOG] 유저 {call.from_user.id}가 실행을 승인함.")
            
        elif call.data == "test_no":
            bot.edit_message_text("❌ 실행이 취소되었습니다.", 
                                call.message.chat.id, 
                                call.message.message_id)

        # 마지막에 반드시 answer_callback_query를 호출해야 텔레그램 상단 시계 로딩이 사라집니다.
        bot.answer_callback_query(call.id)