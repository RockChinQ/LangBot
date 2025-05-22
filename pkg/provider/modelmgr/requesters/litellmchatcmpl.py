from __future__ import annotations

import typing
import asyncio
import litellm

from .. import errors, requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class LiteLLMChatCompletions(requester.LLMAPIRequester):
    """LiteLLM ChatCompletion API 请求器，支持多种LLM平台"""

    default_config: dict[str, typing.Any] = {
        'provider': '',  # 使用LiteLLM的provider参数
        'timeout': 120,
    }

    async def initialize(self):
        pass

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.Optional[typing.List[tools_entities.LLMFunction]] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        req_messages = []
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')
            if isinstance(content, list):
                processed_content = []
                for item in content:
                    if item.get('type') == 'text':
                        processed_content.append({"type": "text", "text": item.get('text')})
                    elif item.get('type') == 'image_url' and item.get('image_url'):
                        processed_content.append({
                            "type": "image_url",
                            "image_url": {"url": item.get('image_url').get('url')}
                        })
                    elif item.get('type') == 'image_base64':
                        processed_content.append({
                            "type": "image_url",
                            "image_url": {"url": item.get('image_base64')}
                        })
                msg_dict['content'] = processed_content
            req_messages.append(msg_dict)

        args = extra_args.copy()
        args['model'] = model.model_entity.name
        args['messages'] = req_messages
        
        if self.requester_cfg.get('provider'):
            args['api_base'] = self.requester_cfg.get('api_base', '')
            args['api_version'] = self.requester_cfg.get('api_version', '')
            args['model'] = f"{self.requester_cfg['provider']}/{model.model_entity.name}"

        api_key = model.token_mgr.get_token()
        
        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(funcs)
            if tools:
                args['tools'] = tools

        try:
            response = await asyncio.to_thread(
                litellm.completion,
                api_key=api_key,
                timeout=self.requester_cfg.get('timeout', 120),
                **args
            )
            
            if not response or not response.choices:
                raise errors.RequesterError('接口返回为空，请确定模型提供商服务是否正常')
            
            choice = response.choices[0]
            message_data = {
                'role': choice.message.role or 'assistant',
                'content': choice.message.content or '',
            }
            
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                tool_calls = []
                for tool_call in choice.message.tool_calls:
                    tool_calls.append(
                        llm_entities.ToolCall(
                            id=tool_call.id,
                            type='function',
                            function=llm_entities.FunctionCall(
                                name=tool_call.function.name,
                                arguments=tool_call.function.arguments
                            )
                        )
                    )
                message_data['tool_calls'] = tool_calls
            
            return llm_entities.Message(**message_data)
            
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
        except Exception as e:
            raise errors.RequesterError(f'请求错误: {str(e)}')
