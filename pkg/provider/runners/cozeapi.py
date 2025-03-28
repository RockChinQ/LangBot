from __future__ import annotations

import typing
import json
import time
from datetime import datetime
import aiohttp
from cozepy import TokenAuth, Message, ChatStatus, ChatEventType, WorkflowEventType, Stream, WorkflowEvent,AsyncCoze

from .. import runner
from ...core import entities as core_entities
from .. import entities as llm_entities


class CozeAPIError(Exception):
    """Coze API 请求失败"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@runner.runner_class("coze-app-api")
class CozeAPIRunner(runner.RequestRunner):
    """Coze API对话请求器"""
    
    # 运行器内部使用的配置
    app_type: str                   # 应用类型 (agent/workflow)
    coze_www_base: str           # Coze平台基础URL
    coze_api_base: str           # Coze API基础URL
    stream: bool = True           # 是否使用流式输出
    bot_id: str = None           # 机器人ID
    app_id: str = None          # 应用ID
    flow_id: str = None          # 工作流ID
    coze_client: AsyncCoze = None     # Coze客户端实例
    # access_token: str = None      # 访问令牌
    # token_expires_at: int = 0     # 令牌过期时间
    token_auth :TokenAuth = None  #鉴权
    input_key: str = "input"     # 输入键
    pat: str


    async def initialize(self):
        """初始化"""
        valid_app_types = ["agent", "workflow"]
        self.app_type = self.ap.provider_cfg.data["coze-app-api"]["app-type"]
        
        # 检查配置文件中使用的应用类型是否支持
        if (self.app_type not in valid_app_types):
            raise CozeAPIError(
                f"不支持的 Coze 应用类型: {self.app_type}"
            )
        
        # 初始化Coze参数配置
        coze_config = self.ap.provider_cfg.data["coze-app-api"]
        # self.client_type = coze_config["client_type"] 
        # self.client_id = coze_config["client_id"]
        
        self.pat_token = coze_config["pat_token"]
        self.coze_www_base = coze_config["coze_www_base"]
        self.coze_api_base = coze_config["coze_api_base"]
        self.stream = coze_config.get("stream", True)
        
        # 根据应用类型获取对应的bot_id和flow_id
        if self.app_type == "agent":
            self.bot_id = coze_config["agent"]["bot_id"]
        else:  # workflow
            # 工作流模式下，bot_id是可选的
            workflow_config = coze_config["workflow"]
            self.bot_id = workflow_config.get("bot_id", None) 
            if "flow_id" not in workflow_config:
                raise CozeAPIError("工作流模式下必须提供 flow_id")
            self.flow_id = workflow_config["flow_id"]
            self.app_id = workflow_config.get("app_id", None)
            
            if self.app_id and self.bot_id:
                raise CozeAPIError("app_id和bot_id不能同时存在")
            
            if not self.app_id and not self.bot_id:
                raise CozeAPIError("app_id和bot_id不能同时不存在")
            self.input_key = workflow_config.get("input_key", "input")

        
        # config = {
        #     "client_type": self.client_type,
        #     "client_id": self.client_id,
        #     "coze_www_base": self.coze_www_base,
        #     "coze_api_base": self.coze_api_base,
        #     "pat": self.pat,
        # }
        self.token_auth = TokenAuth(self.pat_token)

        
        # 获取访问令牌
        # await self._ensure_access_token()
        
        # 初始化Coze客户端
        self.coze_client = AsyncCoze(
            auth=self.token_auth,
            base_url=self.coze_api_base
        )

    # async def _ensure_access_token(self):
    #     """确保访问令牌有效"""
    #     current_time = int(time.time())
    #     # print('access_token: ', self.access_token)
    #     # print('token_expires_at: ', self.token_expires_at)
        
    #     if not self.access_token or current_time + 300 >= self.token_expires_at:
    #         oauth_token = self.oauth_app.get_access_token()
    #         self.access_token = oauth_token.access_token
    #         self.token_expires_at = oauth_token.expires_in

    async def _preprocess_user_message(
        self, query: core_entities.Query
    ) -> str:
        """预处理用户消息，提取纯文本"""
        plain_text = ""
        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == "text":
                    plain_text += ce.text
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content
        return plain_text
     
    async def _agent_messages(
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """Coze 智能体对话请求"""
        
        plain_text = await self._preprocess_user_message(query)
        
        if self.stream:
            # 流式输出模式
            async for event in self.coze_client.chat.stream(
                bot_id=self.bot_id,
                user_id=query.sender_id,  
                conversation_id=query.session.using_conversation.uuid,
                additional_messages=[
                    Message.build_user_question_text(plain_text),
                ],
            ):
                if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    if event.message.content:
                        yield llm_entities.Message(
                            role="assistant",
                            content=event.message.content,
                        )
                
                if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                    if event.chat.conversation_id:
                        query.session.using_conversation.uuid = event.chat.conversation_id
        else:
            chat = await self.coze_client.chat.create(
                bot_id=self.bot_id,
                user_id=query.sender_id,
                conversation_id=query.session.using_conversation.uuid,
                additional_messages=[
                    Message.build_user_question_text(plain_text)
                ],
            )
            
            #等待回答
            while chat.status == ChatStatus.IN_PROGRESS:
                chat = await self.coze_client.chat.get(chat.id)
            
            if chat.status == ChatStatus.COMPLETED:
                pass



    # 工作流对话请求    
    async def _workflow_messages(
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """Coze 工作流对话请求"""
        
        plain_text = await self._preprocess_user_message(query)
        
        if self.stream:
            # 流式输出模式
            def handle_workflow_iterator(stream: Stream[WorkflowEvent]):
                for event in stream:
                    if event.event == WorkflowEventType.MESSAGE:
                        yield llm_entities.Message(
                            role="assistant",
                            content=event.message,
                        )
                    elif event.event == WorkflowEventType.ERROR:
                        raise CozeAPIError(f"工作流执行错误: {event.error}")
                    elif event.event == WorkflowEventType.INTERRUPT:
                        # 处理中断事件
                        interrupt_stream = self.coze_client.workflows.runs.resume(
                            workflow_id=self.flow_id,
                            event_id=event.interrupt.interrupt_data.event_id,
                            resume_data=plain_text,  # 使用用户输入作为恢复数据
                            interrupt_type=event.interrupt.interrupt_data.type,
                        )
                        yield from handle_workflow_iterator(interrupt_stream)
            
            workflow_stream = self.coze_client.workflows.runs.stream(
                workflow_id=self.flow_id,
                parameters={"input": plain_text},  # 将用户输入作为参数传入
            )
            
            async for message in handle_workflow_iterator(workflow_stream):
                yield message
        else:
            # 非流式输出模式
            input_key = self.input_key
            
            # 创建工作流实例
            try:
                if self.app_id:
                    workflow = self.coze_client.workflows.runs.create(
                        workflow_id=self.flow_id,
                        app_id=self.app_id,
                        parameters={input_key: plain_text}
                    )
                else:
                    workflow = self.coze_client.workflows.runs.create(
                        workflow_id=self.flow_id,
                        parameters={input_key: plain_text}
                    )
                
                if workflow.data:
                    # 解析响应数据
                    data = json.loads(workflow.data)
                    if isinstance(data, dict) and "data" in data:
                        answer = data["data"]
                        # 只生成一次响应
                        yield llm_entities.Message(
                            role="assistant",
                            content=str(answer),
                        )
                        # 提前返回，防止重复处理
                        return
            except Exception as e:
                raise CozeAPIError(f"工作流执行错误: {str(e)}")

    async def run(
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行"""
            
        if self.app_type == "agent":
            async for msg in self._agent_messages(query):
                yield msg
        elif self.app_type == "workflow":
            async for msg in self._workflow_messages(query):
                yield msg
        else:
            raise CozeAPIError(
                f"不支持的 Coze 应用类型: {self.app_type}"
            ) 