"""主线使用的会话管理模块

每个人、每个群单独一个session，session内部保留了对话的上下文，
"""

import logging
import threading
import time
import json

import pkg.openai.manager
import pkg.openai.modelmgr
import pkg.database.manager
import pkg.utils.context

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models

# 运行时保存的所有session
sessions = {}


class SessionOfflineStatus:
    ON_GOING = 'on_going'
    EXPLICITLY_CLOSED = 'explicitly_closed'


# 重置session.prompt
def reset_session_prompt(session_name, prompt):
    # 备份原始数据
    bak_path = 'logs/{}-{}.bak'.format(
        session_name,
        time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    )
    f = open(bak_path, 'w+')
    f.write(prompt)
    f.close()
    # 生成新数据
    config = pkg.utils.context.get_config()
    prompt = [
        {
            'role': 'system',
            'content': config.default_prompt['default'] if type(config.default_prompt) == dict else config.default_prompt
        }
    ]
    # 警告
    logging.warning(
        """
用户[{}]的数据已被重置，有可能是因为数据版本过旧或存储错误
原始数据将备份在：
{}""".format(session_name, bak_path)
    )  # 为保证多行文本格式正确故无缩进
    return prompt


# 从数据加载session
def load_sessions():
    """从数据库加载sessions"""

    global sessions

    db_inst = pkg.utils.context.get_database_manager()

    session_data = db_inst.load_valid_sessions()

    for session_name in session_data:
        logging.info('加载session: {}'.format(session_name))

        temp_session = Session(session_name)
        temp_session.name = session_name
        temp_session.create_timestamp = session_data[session_name]['create_timestamp']
        temp_session.last_interact_timestamp = session_data[session_name]['last_interact_timestamp']
        try:
            temp_session.prompt = json.loads(session_data[session_name]['prompt'])
            temp_session.token_counts = json.loads(session_data[session_name]['token_counts'])
        except Exception:
            temp_session.prompt = reset_session_prompt(session_name, session_data[session_name]['prompt'])
            temp_session.persistence()
        temp_session.default_prompt = json.loads(session_data[session_name]['default_prompt']) if \
            session_data[session_name]['default_prompt'] else []

        sessions[session_name] = temp_session


# 获取指定名称的session，如果不存在则创建一个新的
def get_session(session_name: str):
    global sessions
    if session_name not in sessions:
        sessions[session_name] = Session(session_name)
    return sessions[session_name]


def dump_session(session_name: str):
    global sessions
    if session_name in sessions:
        assert isinstance(sessions[session_name], Session)
        sessions[session_name].persistence()
        del sessions[session_name]


# 通用的OpenAI API交互session
# session内部保留了对话的上下文，
# 收到用户消息后，将上下文提交给OpenAI API生成回复
class Session:
    name = ''

    prompt = []
    """使用list来保存会话中的回合"""

    token_counts = []
    """每个回合的token数量"""

    default_prompt = []
    """本session的默认prompt"""

    create_timestamp = 0
    """会话创建时间"""

    last_interact_timestamp = 0
    """上次交互(产生回复)时间"""

    just_switched_to_exist_session = False

    response_lock = None

    # 加锁
    def acquire_response_lock(self):
        logging.debug('{},lock acquire,{}'.format(self.name, self.response_lock))
        self.response_lock.acquire()
        logging.debug('{},lock acquire successfully,{}'.format(self.name, self.response_lock))

    # 释放锁
    def release_response_lock(self):
        if self.response_lock.locked():
            logging.debug('{},lock release,{}'.format(self.name, self.response_lock))
            self.response_lock.release()
            logging.debug('{},lock release successfully,{}'.format(self.name, self.response_lock))

    # 从配置文件获取会话预设信息
    def get_default_prompt(self, use_default: str = None):
        import pkg.openai.dprompt as dprompt

        if use_default is None:
            use_default = dprompt.mode_inst().get_using_name()

        current_default_prompt, _ = dprompt.mode_inst().get_prompt(use_default)
        return current_default_prompt

    def __init__(self, name: str):
        self.name = name
        self.create_timestamp = int(time.time())
        self.last_interact_timestamp = int(time.time())
        self.prompt = []
        self.token_counts = []
        self.schedule()

        self.response_lock = threading.Lock()

        self.default_prompt = self.get_default_prompt()
        logging.debug("prompt is: {}".format(self.default_prompt))

    # 设定检查session最后一次对话是否超过过期时间的计时器
    def schedule(self):
        threading.Thread(target=self.expire_check_timer_loop, args=(self.create_timestamp,)).start()

    # 检查session是否已经过期
    def expire_check_timer_loop(self, create_timestamp: int):
        global sessions
        while True:
            time.sleep(60)

            # 不是此session已更换，退出
            if self.create_timestamp != create_timestamp or self not in sessions.values():
                return

            config = pkg.utils.context.get_config()
            if int(time.time()) - self.last_interact_timestamp > config.session_expire_time:
                logging.info('session {} 已过期'.format(self.name))

                # 触发插件事件
                args = {
                    'session_name': self.name,
                    'session': self,
                    'session_expire_time': config.session_expire_time
                }
                event = pkg.plugin.host.emit(plugin_models.SessionExpired, **args)
                if event.is_prevented_default():
                    return

                self.reset(expired=True, schedule_new=False)

                # 删除此session
                del sessions[self.name]
                return

    # 请求回复
    # 这个函数是阻塞的
    def append(self, text: str) -> str:
        """向session中添加一条消息，返回接口回复"""

        self.last_interact_timestamp = int(time.time())

        # 触发插件事件
        if not self.prompt:
            args = {
                'session_name': self.name,
                'session': self,
                'default_prompt': self.default_prompt,
            }

            event = pkg.plugin.host.emit(plugin_models.SessionFirstMessageReceived, **args)
            if event.is_prevented_default():
                return None

        config = pkg.utils.context.get_config()
        max_length = config.prompt_submit_length

        prompts, counts = self.cut_out(text, max_length)

        # 计算请求前的prompt数量
        total_token_before_query = 0
        for token_count in counts:
            total_token_before_query += token_count

        # 向API请求补全
        message, total_token = pkg.utils.context.get_openai_manager().request_completion(
            prompts,
        )

        # 成功获取，处理回复
        res_test = message
        res_ans = res_test.strip()

        # 将此次对话的双方内容加入到prompt中
        self.prompt.append({'role': 'user', 'content': text})
        self.prompt.append({'role': 'assistant', 'content': res_ans})

        # 向token_counts中添加本回合的token数量
        self.token_counts.append(total_token-total_token_before_query)
        logging.debug("本回合使用token: {}, session counts: {}".format(total_token-total_token_before_query, self.token_counts))

        if self.just_switched_to_exist_session:
            self.just_switched_to_exist_session = False
            self.set_ongoing()

        return res_ans if res_ans[0] != '\n' else res_ans[1:]

    # 删除上一回合并返回上一回合的问题
    def undo(self) -> str:
        self.last_interact_timestamp = int(time.time())

        # 删除最后两个消息
        if len(self.prompt) < 2:
            raise Exception('之前无对话，无法撤销')

        question = self.prompt[-2]['content']
        self.prompt = self.prompt[:-2]
        self.token_counts = self.token_counts[:-1]

        # 返回上一回合的问题
        return question

    # 构建对话体
    def cut_out(self, msg: str, max_tokens: int) -> tuple[list, list]:
        """将现有prompt进行切割处理，使得新的prompt长度不超过max_tokens

        :return: (新的prompt, 新的token_counts)
        """

        # 最终由三个部分组成
        # - default_prompt         情景预设固定值
        # - changable_prompts      可变部分, 此会话中的历史对话回合
        # - current_question       当前问题

        # 包装目前的对话回合内容
        changable_prompts = []
        changable_counts = []
        # 倒着来, 遍历prompt的步长为2, 遍历tokens_counts的步长为1
        changable_index = len(self.prompt) - 1
        token_count_index = len(self.token_counts) - 1

        packed_tokens = 0

        while changable_index >= 0 and token_count_index >= 0:
            if packed_tokens + self.token_counts[token_count_index] > max_tokens:
                break

            changable_prompts.insert(0, self.prompt[changable_index])
            changable_prompts.insert(0, self.prompt[changable_index - 1])
            changable_counts.insert(0, self.token_counts[token_count_index])
            packed_tokens += self.token_counts[token_count_index]

            changable_index -= 2
            token_count_index -= 1

        # 将default_prompt和changable_prompts合并
        result_prompt = self.default_prompt + changable_prompts

        # 添加当前问题
        result_prompt.append(
            {
                'role': 'user',
                'content': msg
            }
        )

        logging.debug('cut_out: {}\nchangable section tokens: {}\npacked counts: {}\nsession counts: {}'.format(json.dumps(result_prompt, ensure_ascii=False, indent=4),
                                                                             packed_tokens,
                                                                             changable_counts,
                                                                             self.token_counts))

        return result_prompt, changable_counts

    # 持久化session
    def persistence(self):
        if self.prompt == self.get_default_prompt():
            return

        db_inst = pkg.utils.context.get_database_manager()

        name_spt = self.name.split('_')

        subject_type = name_spt[0]
        subject_number = int(name_spt[1])

        db_inst.persistence_session(subject_type, subject_number, self.create_timestamp, self.last_interact_timestamp,
                                    json.dumps(self.prompt), json.dumps(self.default_prompt), json.dumps(self.token_counts))

    # 重置session
    def reset(self, explicit: bool = False, expired: bool = False, schedule_new: bool = True, use_prompt: str = None):
        if self.prompt:
            self.persistence()
            if explicit:
                # 触发插件事件
                args = {
                    'session_name': self.name,
                    'session': self
                }

                # 此事件不支持阻止默认行为
                _ = pkg.plugin.host.emit(plugin_models.SessionExplicitReset, **args)

                pkg.utils.context.get_database_manager().explicit_close_session(self.name, self.create_timestamp)

            if expired:
                pkg.utils.context.get_database_manager().set_session_expired(self.name, self.create_timestamp)

        self.default_prompt = self.get_default_prompt(use_prompt)
        self.prompt = []
        self.token_counts = []
        self.create_timestamp = int(time.time())
        self.last_interact_timestamp = int(time.time())
        self.just_switched_to_exist_session = False

        # self.response_lock = threading.Lock()

        if schedule_new:
            self.schedule()

    # 将本session的数据库状态设置为on_going
    def set_ongoing(self):
        pkg.utils.context.get_database_manager().set_session_ongoing(self.name, self.create_timestamp)

    # 切换到上一个session
    def last_session(self):
        last_one = pkg.utils.context.get_database_manager().last_session(self.name, self.last_interact_timestamp)
        if last_one is None:
            return None
        else:
            self.persistence()

            self.create_timestamp = last_one['create_timestamp']
            self.last_interact_timestamp = last_one['last_interact_timestamp']
            try:
                self.prompt = json.loads(last_one['prompt'])
                self.token_counts = json.loads(last_one['token_counts'])
            except json.decoder.JSONDecodeError:
                self.prompt = reset_session_prompt(self.name, last_one['prompt'])
                self.persistence()
            self.default_prompt = json.loads(last_one['default_prompt']) if last_one['default_prompt'] else []

            self.just_switched_to_exist_session = True
            return self

    # 切换到下一个session
    def next_session(self):
        next_one = pkg.utils.context.get_database_manager().next_session(self.name, self.last_interact_timestamp)
        if next_one is None:
            return None
        else:
            self.persistence()

            self.create_timestamp = next_one['create_timestamp']
            self.last_interact_timestamp = next_one['last_interact_timestamp']
            try:
                self.prompt = json.loads(next_one['prompt'])
                self.token_counts = json.loads(next_one['token_counts'])
            except json.decoder.JSONDecodeError:
                self.prompt = reset_session_prompt(self.name, next_one['prompt'])
                self.persistence()
            self.default_prompt = json.loads(next_one['default_prompt']) if next_one['default_prompt'] else []

            self.just_switched_to_exist_session = True
            return self

    def list_history(self, capacity: int = 10, page: int = 0):
        return pkg.utils.context.get_database_manager().list_history(self.name, capacity, page)

    def delete_history(self, index: int) -> bool:
        return pkg.utils.context.get_database_manager().delete_history(self.name, index)

    def delete_all_history(self) -> bool:
        return pkg.utils.context.get_database_manager().delete_all_history(self.name)

    def draw_image(self, prompt: str):
        return pkg.utils.context.get_openai_manager().request_image(prompt)
