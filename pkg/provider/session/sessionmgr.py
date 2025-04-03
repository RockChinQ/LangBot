from __future__ import annotations

import asyncio

from ...core import app, entities as core_entities
from ...plugin import context as plugin_context
from ...provider import entities as provider_entities


class SessionManager:
    """会话管理器
    """

    ap: app.Application

    session_list: list[core_entities.Session]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.session_list = []

    async def initialize(self):
        pass

    async def get_session(self, query: core_entities.Query) -> core_entities.Session:
        """获取会话
        """
        for session in self.session_list:
            if query.launcher_type == session.launcher_type and query.launcher_id == session.launcher_id:
                return session

        session_concurrency = self.ap.system_cfg.data['session-concurrency']['default']

        if f'{query.launcher_type.value}_{query.launcher_id}' in self.ap.system_cfg.data['session-concurrency']:
            session_concurrency = self.ap.system_cfg.data['session-concurrency'][f'{query.launcher_type.value}_{query.launcher_id}']

        session = core_entities.Session(
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            semaphore=asyncio.Semaphore(session_concurrency),
        )
        self.session_list.append(session)
        return session

    async def get_conversation(self, query: core_entities.Query, session: core_entities.Session, pipeline_config: dict) -> core_entities.Conversation:
        """获取对话或创建对话"""

        if not session.conversations:
            session.conversations = []

        # set prompt
        prompt_messages = []

        for prompt_message in pipeline_config['ai']['local-agent']['prompt']:
            prompt_messages.append(provider_entities.Message(**prompt_message))

        prompt = provider_entities.Prompt(
            name="default",
            messages=prompt_messages,
        )

        if session.using_conversation is None:
            conversation = core_entities.Conversation(
                prompt=prompt,
                messages=[],
                use_llm_model=await self.ap.model_mgr.get_model_by_uuid(
                    query.pipeline_config['ai']['local-agent']['model']
                ),
                use_funcs=await self.ap.tool_mgr.get_all_functions(
                    plugin_enabled=True,
                ),
            )
            session.conversations.append(conversation)
            session.using_conversation = conversation

        return session.using_conversation
