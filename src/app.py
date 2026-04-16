import telebot
import telebot.apihelper as apihelper

from . import config
from . import handlers


def main():
    bot = telebot.TeleBot(config.BOT_TOKEN)
    apihelper.CONNECT_TIMEOUT = 10
    apihelper.READ_TIMEOUT = 15
    handlers.register_handlers(bot)
    # load persisted projects
    try:
        from . import utils
        utils.load_projects()
    except Exception:
        pass

    print("🚀 AMEVA-Conductor (modular) 시작됨. 지휘를 시작하세요!")
    try:
        bot.polling(non_stop=True, interval=0, timeout=10, long_polling_timeout=20)
    except KeyboardInterrupt:
        print("봇이 수동으로 중지되었습니다.")
    except Exception as e:
        print(f"봇 실행 중 오류: {e}")


if __name__ == '__main__':
    main()
