import quart

from .....core import app
from .. import group


@group.group_class('settings', '/api/v1/settings')
class SettingsRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            return self.success(
                data={
                    "managers": [
                        {
                            "name": m.name,
                            "description": m.description,
                        }
                        for m in self.ap.settings_mgr.get_manager_list()
                    ]
                }
            )
        
        @self.route('/<manager_name>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(manager_name: str) -> str:

            manager = self.ap.settings_mgr.get_manager(manager_name)

            if manager is None:
                return self.fail(1, '配置管理器不存在')

            return self.success(
                data={
                    "manager": {
                        "name": manager.name,
                        "description": manager.description,
                        "schema": manager.schema,
                        "file": manager.file.config_file_name,
                        "data": manager.data,
                        "doc_link": manager.doc_link
                    }
                }
            )
        
        @self.route('/<manager_name>/data', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN)
        async def _(manager_name: str) -> str:
            data = await quart.request.json
            manager = self.ap.settings_mgr.get_manager(manager_name)

            if manager is None:
                return self.fail(code=1, msg='配置管理器不存在')

            # manager.data = data['data']
            for k, v in data['data'].items():
                manager.data[k] = v

            await manager.dump_config()
            return self.success(data={
                "data": manager.data
            })
