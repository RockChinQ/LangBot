import quart
from .. import group

@group.group_class('knowledge_base', '/api/v1/knowledge/bases')
class KnowledgeBaseRouterGroup(group.RouterGroup):

    # 定义成功方法
    def success(self, code=0, data=None, msg: str = 'ok') -> quart.Response:
        return quart.jsonify({
            "code": code,
            "data": data or {},
            "msg": msg
        })
    

        
    async def initialize(self) -> None:


        @self.route('', methods=['POST', 'GET'])
        async def _() -> str:
            
            if quart.request.method == 'GET':
                knowledge_bases = await self.ap.knowledge_base_service.get_all_knowledge_bases()
                bases_list = [
                    {
                        "uuid": kb.id,
                        "name": kb.name,
                        "description": kb.description,
                    } for kb in knowledge_bases
                ]
                return self.success(code=0,
                                    data={'bases': bases_list},
                                    msg='ok')

            json_data = await quart.request.json
            knowledge_base_uuid = await self.ap.knowledge_base_service.create_knowledge_base(
                json_data.get('name'),
                json_data.get('description')
            )
            return self.success(code=0,
                                data={},
                                msg='ok')


        @self.route('/<knowledge_base_uuid>', methods=['GET','DELETE'])
        async def _(knowledge_base_uuid: str) -> str:
            if quart.request.method == 'GET':
                knowledge_base = await self.ap.knowledge_base_service.get_knowledge_base_by_id(knowledge_base_uuid)

                if knowledge_base is None:
                    return self.http_status(404, -1, 'knowledge base not found')

                return self.success(
                    code=0,
                    data={
                        "name": knowledge_base.name,
                        "description": knowledge_base.description,
                        "uuid": knowledge_base.id
                    },
                    msg='ok'
                )
            elif quart.request.method == 'DELETE':
                await self.ap.knowledge_base_service.delete_kb_by_id(knowledge_base_uuid)
                return self.success(code=0, msg='ok')

        @self.route('/<knowledge_base_uuid>/files', methods=['GET'])
        async def _(knowledge_base_uuid: str) -> str:
            if quart.request.method == 'GET':
                files = await self.ap.knowledge_base_service.get_files_by_knowledge_base(knowledge_base_uuid)
                return self.success(code=0,data=[{
                    "id": file.id,
                    "file_name": file.file_name,
                    "status": file.status
                } for file in files],msg='ok')
            
        # delete specific file in knowledge base
        @self.route('/<knowledge_base_uuid>/files/<file_id>', methods=['DELETE'])
        async def _(knowledge_base_uuid: str, file_id: str) -> str:
            await self.ap.knowledge_base_service.delete_data_by_file_id(file_id)
            return self.success(code=0, msg='ok')
        
