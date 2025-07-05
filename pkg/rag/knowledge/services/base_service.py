# 封装异步操作
import asyncio
import logging
from pkg.rag.knowledge.services.database import SessionLocal 

class BaseService:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_session_factory = SessionLocal

    async def _run_sync(self, func, *args, **kwargs):
        """
        在单独的线程中运行同步函数。
        如果第一个参数是 session，则在 to_thread 中获取新的 session。
        """
        
        if getattr(func, '__name__', '').startswith('_db_'): 
            session = await asyncio.to_thread(self.db_session_factory)
            try:
                result = await asyncio.to_thread(func, session, *args, **kwargs)
                return result
            finally:
                session.close()
        else:
            # 否则，直接运行同步函数
            return await asyncio.to_thread(func, *args, **kwargs)