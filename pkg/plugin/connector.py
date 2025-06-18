# For connect to plugin runtime.
from __future__ import annotations

import asyncio
import os
import sys

from ..core import app
from . import handler
from ..utils import platform
from langbot_plugin.runtime.io.controllers.stdio import client as stdio_client_controller
from langbot_plugin.runtime.io.connections import stdio as stdio_connection
from langbot_plugin.runtime.io.controllers.ws import client as ws_client_controller
from langbot_plugin.api.entities import events, context


class PluginRuntimeConnector:
    """Plugin runtime connector"""

    ap: app.Application

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    stdio_client_controller: stdio_client_controller.StdioClientController

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        async def new_connection_callback(connection: stdio_connection.StdioConnection):
            self.handler = handler.RuntimeConnectionHandler(connection, self.ap)
            self.handler_task = asyncio.create_task(self.handler.run())
            _ = await self.handler.ping()
            self.ap.logger.info('Connected to plugin runtime.')
            await self.handler_task

        task: asyncio.Task | None = None

        if platform.get_platform() == 'docker':  # use websocket
            self.ap.logger.info('use websocket to connect to plugin runtime')
            ws_url = self.ap.instance_config.data['plugin']['runtime_ws_url']
            ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
            )
            task = ctrl.run(new_connection_callback)
        else:  # stdio
            self.ap.logger.info('use stdio to connect to plugin runtime')
            # cmd: lbp rt -s
            python_path = sys.executable
            env = os.environ.copy()
            ctrl = stdio_client_controller.StdioClientController(
                command=python_path,
                args=['-m', 'langbot_plugin.cli.__init__', 'rt', '-s'],
                env=env,
            )
            task = ctrl.run(new_connection_callback)

        asyncio.create_task(task)

    async def initialize_plugins(self):
        pass

    async def emit_event(
        self,
        event: events.BaseEventModel,
    ) -> context.EventContext:
        pass
