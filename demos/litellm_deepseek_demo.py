"""
LiteLLM DeepSeek 集成演示

此脚本演示如何使用 LiteLLM 集成来支持 DeepSeek 模型。
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkg.core.app import Application
from pkg.core.entities import Query, Session, LifecycleControlScope
from pkg.provider.entities import Message, ContentElement
from pkg.provider.modelmgr.modelmgr import LLMModelInfo


async def main():
    app = Application()
    await app.initialize()
    
    print("LiteLLM DeepSeek 集成演示")
    print("=" * 50)
    
    deepseek_api_key = os.environ.get("deepseek_api_key")
    if not deepseek_api_key:
        print("未找到 DeepSeek API 密钥，请设置环境变量 deepseek_api_key")
        return
    
    model_name = "deepseek-chat"
    model_info = LLMModelInfo(
        uuid="temp-deepseek-model",
        name=model_name,
        requester="litellm-chat-completions",
        requester_config={
            "provider": "deepseek",
            "timeout": 120
        },
        token_mgr_config={
            "tokens": [deepseek_api_key]
        }
    )
    
    app.model_mgr.register_model(model_info)
    print(f"已注册临时 DeepSeek 模型: {model_name}")
    
    session = Session(id="demo-session")
    query = Query(
        id="demo-query",
        session=session,
        raw_message="你好，请介绍一下自己",
        platform_user_id="demo-user",
        platform_group_id=None,
    )
    
    messages = [
        Message(
            role="system",
            content=[ContentElement.from_text("你是一个由DeepSeek提供支持的AI助手，通过LiteLLM集成访问。请简要介绍自己。")]
        ),
        Message(
            role="user",
            content=[ContentElement.from_text("你好，请介绍一下自己，并说明你是哪个模型")]
        )
    ]
    
    print("\n发送请求到 DeepSeek 模型...")
    
    try:
        response = await app.model_mgr.invoke_llm(
            query=query,
            model_uuid=model_info.uuid,
            messages=messages,
        )
        
        print("\n模型响应:")
        print("-" * 50)
        if isinstance(response.content, list):
            content_text = " ".join([str(c) for c in response.content])
        else:
            content_text = response.content
        print(content_text)
        print("-" * 50)
        
        print("\n演示完成！")
        
    except Exception as e:
        print(f"\n请求失败: {str(e)}")
    
    app.model_mgr.unregister_model(model_info.uuid)
    print("已清理临时模型")
    
    await app.reload(scope=LifecycleControlScope.APPLICATION)


if __name__ == "__main__":
    asyncio.run(main())
