# QChatGPT 终端启动入口
# 在此层级解决依赖项检查。

asciiart = r"""
  ___   ___ _         _    ___ ___ _____ 
 / _ \ / __| |_  __ _| |_ / __| _ \_   _|
| (_) | (__| ' \/ _` |  _| (_ |  _/ | |  
 \__\_\\___|_||_\__,_|\__|\___|_|   |_|  

⭐️开源地址: https://github.com/RockChinQ/QChatGPT
📖文档地址: https://q.rkcn.top
"""


async def main_entry():
    print(asciiart)

    import sys

    # 检查依赖

    from pkg.core.bootutils import deps

    missing_deps = await deps.check_deps()

    if missing_deps:
        print("以下依赖包未安装，将自动安装，请完成后重启程序：")
        for dep in missing_deps:
            print("-", dep)
        await deps.install_deps(missing_deps)
        print("已自动安装缺失的依赖包，请重启程序。")
        sys.exit(0)

    # 检查配置文件

    from pkg.core.bootutils import files

    generated_files = await files.generate_files()

    if generated_files:
        print("以下文件不存在，已自动生成，请按需修改配置文件后重启：")
        for file in generated_files:
            print("-", file)

        sys.exit(0)

    from pkg.core import boot
    await boot.main()


if __name__ == '__main__':
    import asyncio

    asyncio.run(main_entry())
