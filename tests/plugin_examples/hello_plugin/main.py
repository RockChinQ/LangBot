from pkg.plugin.models import *
from pkg.plugin.host import EventContext


# 注册插件
@register(name="Hello", description="hello world", version="0.1", author="RockChinQ")
class HelloPlugin(Plugin):

    def __init__(self):
        pass

    # 当收到个人消息时触发
    @on(PersonNormalMessageReceived)
    def person_normal_message_received(self, event: EventContext, **kwargs):
        msg = kwargs['text_message']
        if msg == "hello":  # 如果消息为hello

            # 输出调试信息
            logging.debug("hello, {}".format(kwargs['sender_id']))

            # 回复消息 "hello, <发送者id>!"
            event.add_return("reply", ["hello, {}!".format(kwargs['sender_id'])])

            # 阻止该事件默认行为（向接口获取回复）
            event.prevent_default()

    # 当收到群消息时触发
    @on(GroupNormalMessageReceived)
    def group_normal_message_received(self, event: EventContext, **kwargs):
        msg = kwargs['text_message']
        if msg == "hello":  # 如果消息为hello

            # 输出调试信息
            logging.debug("hello, {}".format(kwargs['sender_id']))

            # 回复消息 "hello, everyone!"
            event.add_return("reply", ["hello, everyone!"])

            # 阻止该事件默认行为（向接口获取回复）
            event.prevent_default()

    def __del__(self):
        pass