"""
简单的 LiteLLM 集成测试

此脚本使用 LiteLLM 直接调用 DeepSeek API，不依赖 LangBot 的完整启动流程。
"""

import os
import sys
import asyncio
import litellm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pkg.provider.entities import Message, ContentElement


async def main():
    print("LiteLLM DeepSeek 简单集成测试")
    print("=" * 50)
    
    deepseek_api_key = os.environ.get("deepseek_api_key")
    if not deepseek_api_key:
        print("未找到 DeepSeek API 密钥，请设置环境变量 deepseek_api_key")
        return
    
    model_name = "deepseek/deepseek-chat"
    
    print(f"使用模型: {model_name}")
    
    messages = [
        {
            "role": "system",
            "content": "你是一个由DeepSeek提供支持的AI助手，通过LiteLLM集成访问。请简要介绍自己。"
        },
        {
            "role": "user",
            "content": "你好，请介绍一下自己，并说明你是哪个模型"
        }
    ]
    
    print("\n发送请求到 DeepSeek 模型...")
    
    try:
        response = await asyncio.to_thread(
            litellm.completion,
            model=model_name,
            messages=messages,
            api_key=deepseek_api_key
        )
        
        print("\n模型响应:")
        print("-" * 50)
        print(response.choices[0].message.content)
        print("-" * 50)
        
        print("\n演示完成！")
        
    except Exception as e:
        print(f"\n请求失败: {str(e)}")
        print(f"错误详情: {str(e.__class__.__name__)}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
