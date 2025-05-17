"""
LiteLLM 集成演示

此脚本演示如何使用 LiteLLM 集成来支持多种 LLM 平台。
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkg.core.app import Application
from pkg.core.entities import Query, Session
from pkg.provider.entities import Message, ContentElement


async def main():
    app = Application()
    await app.initialize()
    
    print("LiteLLM 集成演示")
    print("=" * 50)
    
    models = app.model_mgr.llm_models
    litellm_models = [m for m in models if m.model_entity.requester == "litellm-chat-completions"]
    
    if not litellm_models:
        print("未找到 LiteLLM 模型，请确保已正确配置 LiteLLM 请求器")
        return
    
    print(f"找到 {len(litellm_models)} 个 LiteLLM 模型")
    for i, model in enumerate(litellm_models):
        print(f"{i+1}. {model.model_entity.name} ({model.model_entity.requester})")
    
    model_idx = 0
    if len(litellm_models) > 1:
        model_idx = int(input("\n请选择要使用的模型 (输入序号): ")) - 1
    
    selected_model = litellm_models[model_idx]
    print(f"\n已选择模型: {selected_model.model_entity.name}")
    
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
            content=[ContentElement.from_text("你是一个由LiteLLM提供支持的AI助手。请简要介绍自己，并说明你是通过LiteLLM集成访问的。")]
        ),
        Message(
            role="user",
            content=[ContentElement.from_text("你好，请介绍一下自己")]
        )
    ]
    
    print("\n发送请求到模型...")
    
    try:
        response = await app.model_mgr.invoke_llm(
            query=query,
            model_uuid=selected_model.model_entity.uuid,
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
    
    from pkg.core.entities import LifecycleControlScope
    await app.reload(scope=LifecycleControlScope.APPLICATION)


if __name__ == "__main__":
    asyncio.run(main())
