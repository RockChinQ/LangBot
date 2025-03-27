from __future__ import annotations

import json
import os
import sys
import logging
import asyncio
import traceback
import sqlalchemy

from .sources import qqofficial

#     FriendMessage, Image, MessageChain, Plain
from ..platform import adapter as msadapter

from ..core import app, entities as core_entities, taskmgr
from ..plugin import events
from .types import message as platform_message
from .types import events as platform_events
from .types import entities as platform_entities

from ..discover import engine

from ..entity.persistence import bot as persistence_bot

# 处理 3.4 移除了 YiriMirai 之后，插件的兼容性问题
from . import types as mirai
sys.modules['mirai'] = mirai


class RuntimeBot:
    """运行时机器人"""

    ap: app.Application

    bot_entity: persistence_bot.Bot

    enable: bool

    adapter: msadapter.MessagePlatformAdapter

    task_wrapper: taskmgr.TaskWrapper

    task_context: taskmgr.TaskContext

    def __init__(self, ap: app.Application, bot_entity: persistence_bot.Bot, adapter: msadapter.MessagePlatformAdapter):
        self.ap = ap
        self.bot_entity = bot_entity
        self.enable = bot_entity.enable
        self.adapter = adapter
        self.task_context = taskmgr.TaskContext()

    async def run(self):

        async def exception_wrapper():
            try:
                self.task_context.set_current_action('Running...')
                await self.adapter.run_async()
                self.task_context.set_current_action('Exited.')
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    self.task_context.set_current_action('Exited.')
                    return
                self.task_context.set_current_action('Exited with error.')
                self.task_context.log(f'平台适配器运行出错: {e}')
                self.task_context.log(f"Traceback: {traceback.format_exc()}")
                self.ap.logger.error(f'平台适配器运行出错: {e}')
                self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")

        self.task_wrapper = self.ap.task_mgr.create_task(
            exception_wrapper(),
            kind="platform-adapter",
            name=f"platform-adapter-{self.adapter.__class__.__name__}",
            context=self.task_context,
            scopes=[core_entities.LifecycleControlScope.APPLICATION, core_entities.LifecycleControlScope.PLATFORM]
        )

    async def shutdown(self):
        await self.adapter.kill()


# 控制QQ消息输入输出的类
class PlatformManager:
    
    # adapter: msadapter.MessageSourceAdapter = None
    adapters: list[msadapter.MessagePlatformAdapter] = []

    message_platform_adapter_components: list[engine.Component] = []

    # ====== 4.0 ======
    ap: app.Application = None

    bots: list[RuntimeBot]

    adapter_components: list[engine.Component]

    adapter_dict: dict[str, type[msadapter.MessagePlatformAdapter]]

    def __init__(self, ap: app.Application = None):

        self.ap = ap
        self.adapters = []
        self.bots = []
        self.adapter_components = []
        self.adapter_dict = {}
    
    async def initialize(self):

        self.adapter_components = self.ap.discover.get_components_by_kind('MessagePlatformAdapter')
        adapter_dict: dict[str, type[msadapter.MessagePlatformAdapter]] = {}
        for component in self.adapter_components:
            adapter_dict[component.metadata.name] = component.get_python_component_class()
        self.adapter_dict = adapter_dict

        await self.load_bots_from_db()

    async def load_bots_from_db(self):
        self.ap.logger.info('Loading bots from db...')

        self.bots = []

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot)
        )

        bots = result.all()
        
        for bot in bots:
            # load all bots here, enable or disable will be handled in runtime
            await self.load_bot(bot)

    async def load_bot(self, bot_entity: persistence_bot.Bot | sqlalchemy.Row[persistence_bot.Bot] | dict) -> RuntimeBot:
        """加载机器人"""
        if isinstance(bot_entity, sqlalchemy.Row):
            bot_entity = persistence_bot.Bot(**bot_entity._mapping)
        elif isinstance(bot_entity, dict):
            bot_entity = persistence_bot.Bot(**bot_entity)
        
        async def on_friend_message(event: platform_events.FriendMessage, adapter: msadapter.MessagePlatformAdapter):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.PERSON,
                launcher_id=event.sender.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain,
                adapter=adapter
            )

        async def on_group_message(event: platform_events.GroupMessage, adapter: msadapter.MessagePlatformAdapter):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.GROUP,
                launcher_id=event.group.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain,
                adapter=adapter
            )

        adapter_inst = self.adapter_dict[bot_entity.adapter](
            bot_entity.adapter_config,
            self.ap
        )

        adapter_inst.register_listener(
            platform_events.FriendMessage,
            on_friend_message
        )
        adapter_inst.register_listener(
            platform_events.GroupMessage,
            on_group_message
        )

        runtime_bot = RuntimeBot(
            ap=self.ap,
            bot_entity=bot_entity,
            adapter=adapter_inst
        )

        self.bots.append(runtime_bot)

        return runtime_bot
    
    async def get_bot_by_uuid(self, bot_uuid: str) -> RuntimeBot | None:
        for bot in self.bots:
            if bot.bot_entity.uuid == bot_uuid:
                return bot
        return None

    async def remove_bot(self, bot_uuid: str):
        for bot in self.bots:
            if bot.bot_entity.uuid == bot_uuid:
                if bot.enable:
                    await bot.shutdown()
                self.bots.remove(bot)
                return

    def get_available_adapters_info(self) -> list[dict]:
        return [
            component.to_plain_dict()
            for component in self.message_platform_adapter_components
        ]

    def get_available_adapter_info_by_name(self, name: str) -> dict | None:
        for component in self.message_platform_adapter_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    async def write_back_config(self, adapter_name: str, adapter_inst: msadapter.MessagePlatformAdapter, config: dict):
        index = -2

        for i, adapter in enumerate(self.adapters):
            if adapter == adapter_inst:
                index = i
                break

        if index == -2:
            raise Exception('平台适配器未找到')

        # 只修改启用的适配器
        real_index = -1

        for i, adapter in enumerate(self.ap.platform_cfg.data['platform-adapters']):
            if adapter['enable']:
                index -= 1
                if index == -1:
                    real_index = i
                    break

        new_cfg = {
            'adapter': adapter_name,
            'enable': True,
            **config
        }
        self.ap.platform_cfg.data['platform-adapters'][real_index] = new_cfg
        await self.ap.platform_cfg.dump_config()

    async def send(self, event: platform_events.MessageEvent, msg: platform_message.MessageChain, adapter: msadapter.MessagePlatformAdapter):
        
        if self.ap.platform_cfg.data['at-sender'] and isinstance(event, platform_events.GroupMessage):

            msg.insert(
                0,
                platform_message.At(
                    event.sender.id
                )
            )

        await adapter.reply_message(
            event,
            msg,
            quote_origin=True if self.ap.platform_cfg.data['quote-origin'] else False
        )

    async def run(self):        
        # This method will only be called when the application launching
        for bot in self.bots:
            if bot.enable:
                await bot.run()

    async def shutdown(self):
        for bot in self.bots:
            if bot.enable:
                await bot.shutdown()
        self.ap.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.PLATFORM)