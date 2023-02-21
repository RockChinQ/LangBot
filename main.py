import importlib
import os
import shutil
import threading
import time

import logging
import sys

try:
    import colorlog
except ImportError:
    # 尝试安装
    import pkg.utils.pkgmgr as pkgmgr
    pkgmgr.install_requirements("requirements.txt")
    try:
        import colorlog
    except ImportError:
        print("依赖不满足,请查看 https://github.com/RockChinQ/qcg-installer/issues/15")
        sys.exit(1)
import colorlog

import requests
import websockets.exceptions
from urllib3.exceptions import InsecureRequestWarning


sys.path.append(".")

log_colors_config = {
    'DEBUG': 'green',  # cyan white
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}


def init_db():
    import pkg.database.manager
    database = pkg.database.manager.DatabaseManager()

    database.initialize_database()


known_exception_caught = False


def reset_logging():
    assert os.path.exists('config.py')

    config = importlib.import_module('config')

    import pkg.utils.context

    if pkg.utils.context.context['logger_handler'] is not None:
        logging.getLogger().removeHandler(pkg.utils.context.context['logger_handler'])

    for handler in logging.getLogger().handlers:
        logging.getLogger().removeHandler(handler)

    logging.basicConfig(level=config.logging_level,  # 设置日志输出格式
                        filename='qchatgpt.log',  # log日志输出的文件位置和文件名
                        format="[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s",
                        # 日志输出的格式
                        # -8表示占位符，让输出左对齐，输出长度都为8位
                        datefmt="%Y-%m-%d %H:%M:%S"  # 时间输出的格式
                        )
    sh = logging.StreamHandler()
    sh.setLevel(config.logging_level)
    sh.setFormatter(colorlog.ColoredFormatter(
        fmt="%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : "
            "%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=log_colors_config
    ))
    logging.getLogger().addHandler(sh)
    pkg.utils.context.context['logger_handler'] = sh
    return sh


def main(first_time_init=False):
    global known_exception_caught

    known_exception_caught = False
    try:
        # 导入config.py
        assert os.path.exists('config.py')

        config = importlib.import_module('config')

        import pkg.utils.context
        pkg.utils.context.set_config(config)

        sh = reset_logging()

        # 检查是否设置了管理员
        if not (hasattr(config, 'admin_qq') and config.admin_qq != 0):
            # logging.warning("未设置管理员QQ,管理员权限指令及运行告警将无法使用,如需设置请修改config.py中的admin_qq字段")
            while True:
                try:
                    config.admin_qq = int(input("未设置管理员QQ,管理员权限指令及运行告警将无法使用,请输入管理员QQ号: "))
                    # 写入到文件

                    # 读取文件
                    config_file_str = ""
                    with open("config.py", "r", encoding="utf-8") as f:
                        config_file_str = f.read()
                    # 替换
                    config_file_str = config_file_str.replace("admin_qq = 0", "admin_qq = " + str(config.admin_qq))
                    # 写入
                    with open("config.py", "w", encoding="utf-8") as f:
                        f.write(config_file_str)

                    print("管理员QQ已设置，如需修改请修改config.py中的admin_qq字段")
                    time.sleep(4)
                    break
                except ValueError:
                    print("请输入数字")

        import pkg.openai.manager
        import pkg.database.manager
        import pkg.openai.session
        import pkg.qqbot.manager

        pkg.utils.context.context['logger_handler'] = sh
        # 主启动流程
        database = pkg.database.manager.DatabaseManager()

        database.initialize_database()

        openai_interact = pkg.openai.manager.OpenAIInteract(config.openai_config['api_key'])

        # 加载所有未超时的session
        pkg.openai.session.load_sessions()

        # 初始化qq机器人
        qqbot = pkg.qqbot.manager.QQBotManager(mirai_http_api_config=config.mirai_http_api_config,
                                               timeout=config.process_message_timeout, retry=config.retry_times,
                                               first_time_init=first_time_init)

        # 加载插件
        import pkg.plugin.host
        pkg.plugin.host.load_plugins()

        pkg.plugin.host.initialize_plugins()

        if first_time_init:  # 不是热重载之后的启动,则不启动新的bot线程

            import mirai.exceptions

            def run_bot_wrapper():
                global known_exception_caught
                try:
                    qqbot.bot.run()
                except TypeError as e:
                    if str(e).__contains__("argument 'debug'"):
                        logging.error(
                            "连接bot失败:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/82".format(e))
                        known_exception_caught = True
                    elif str(e).__contains__("As of 3.10, the *loop*"):
                        logging.error(
                            "Websockets版本过低:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/5".format(e))
                        known_exception_caught = True

                except websockets.exceptions.InvalidStatus as e:
                    logging.error(
                        "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                            e))
                    known_exception_caught = True
                except mirai.exceptions.NetworkError as e:
                    logging.error("连接mirai-api-http失败:{}, 请检查是否已按照文档启动mirai".format(e))
                    known_exception_caught = True
                except Exception as e:
                    if str(e).__contains__("404"):
                        logging.error(
                            "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                                e))
                        known_exception_caught = True
                    elif str(e).__contains__("signal only works in main thread"):
                        logging.error(
                            "hypercorn异常:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/86".format(
                                e))
                        known_exception_caught = True
                    elif str(e).__contains__("did not receive a valid HTTP"):
                        logging.error(
                            "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                                e))
                    else:
                        logging.error(
                            "捕捉到未知异常:{}, 请前往 https://github.com/RockChinQ/QChatGPT/issues 查找或提issue".format(e))
                        known_exception_caught = True
                        raise e

            qq_bot_thread = threading.Thread(target=run_bot_wrapper, args=(), daemon=True)
            qq_bot_thread.start()
    finally:
        time.sleep(12)
        if first_time_init:
            if not known_exception_caught:
                logging.info('程序启动完成,如长时间未显示 ”成功登录到账号xxxxx“ ,并且不回复消息,请查看 '
                             'https://github.com/RockChinQ/QChatGPT/issues/37')
            else:
                sys.exit(1)
        else:
            logging.info('热重载完成')

    # 发送赞赏码
    if hasattr(config, 'encourage_sponsor_at_start') \
        and config.encourage_sponsor_at_start \
        and pkg.utils.context.get_openai_manager().audit_mgr.get_total_text_length() >= 2048:

        logging.info("发送赞赏码")
        from mirai import MessageChain, Plain, Image
        import pkg.utils.constants
        message_chain = MessageChain([
            Plain("自2022年12月初以来，开发者已经花费了大量时间和精力来维护本项目，如果您觉得本项目对您有帮助，欢迎赞赏开发者，"
                  "以支持项目稳定运行😘"),
            Image(base64=pkg.utils.constants.alipay_qr_b64),
            Image(base64=pkg.utils.constants.wechat_qr_b64),
            Plain("BTC: 3N4Azee63vbBB9boGv9Rjf4N5SocMe5eCq\nXMR: 89LS21EKQuDGkyQoe2nDupiuWXk4TVD6FALvSKv5owfmeJEPFpHeMsZLYtLiJ6GxLrhsRe5gMs6MyMSDn4GNQAse2Mae4KE\n\n"),
            Plain("(本消息仅在启动时发送至管理员，如果您不想再看到此消息，请在config.py中将encourage_sponsor_at_start设置为False)")
        ])
        pkg.utils.context.get_qqbot_manager().notify_admin_message_chain(message_chain)

    time.sleep(5)
    import pkg.utils.updater
    try:
        if pkg.utils.updater.is_new_version_available():
            pkg.utils.context.get_qqbot_manager().notify_admin("新版本可用，请发送 !update 进行自动更新")
        else:
            logging.info("当前已是最新版本")

    except Exception as e:
        logging.warning("检查更新失败:{}".format(e))

    while True:
        try:
            time.sleep(10)
            if qqbot != pkg.utils.context.get_qqbot_manager():  # 已经reload了
                logging.info("以前的main流程由于reload退出")
                break
        except KeyboardInterrupt:
            stop()

            print("程序退出")
            sys.exit(0)


def stop():
    import pkg.utils.context
    import pkg.qqbot.manager
    import pkg.openai.session
    try:
        import pkg.plugin.host
        pkg.plugin.host.unload_plugins()

        qqbot_inst = pkg.utils.context.get_qqbot_manager()
        assert isinstance(qqbot_inst, pkg.qqbot.manager.QQBotManager)

        for session in pkg.openai.session.sessions:
            logging.info('持久化session: %s', session)
            pkg.openai.session.sessions[session].persistence()
        pkg.utils.context.get_database_manager().close()
    except Exception as e:
        if not isinstance(e, KeyboardInterrupt):
            raise e


if __name__ == '__main__':
    # 检查是否有config.py,如果没有就把config-template.py复制一份,并退出程序
    if not os.path.exists('config.py'):
        shutil.copy('config-template.py', 'config.py')
        print('请先在config.py中填写配置')
        sys.exit(0)

    # 检查是否有banlist.py,如果没有就把banlist-template.py复制一份
    if not os.path.exists('banlist.py'):
        shutil.copy('banlist-template.py', 'banlist.py')

    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db()
        sys.exit(0)

    elif len(sys.argv) > 1 and sys.argv[1] == 'update':
        try:
            try:
                import pkg.utils.pkgmgr
                pkg.utils.pkgmgr.ensure_dulwich()
            except:
                pass

            from dulwich import porcelain

            repo = porcelain.open_repo('.')
            porcelain.pull(repo)
        except ModuleNotFoundError:
            print("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
        sys.exit(0)

    # import pkg.utils.configmgr
    #
    # pkg.utils.configmgr.set_config_and_reload("quote_origin", False)
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    main(True)
