import quart

from ... import group


@group.group_class('provider/requesters', '/api/v1/provider/requesters')
class RequestersRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> quart.Response:
            return self.success(data={
                'requesters': self.ap.model_mgr.get_available_requesters_info()
            })
        
        @self.route('/<requester_name>', methods=['GET'])
        async def _(requester_name: str) -> quart.Response:

            requester_info = self.ap.model_mgr.get_available_requester_info_by_name(requester_name)

            if requester_info is None:
                return self.http_status(404, -1, 'requester not found')

            return self.success(data={
                'requester': requester_info
            })
