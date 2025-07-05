from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import numpy as np # 用于处理从LargeBinary转换回来的embedding

Base = declarative_base()

class KnowledgeBase(Base):
    __tablename__ = 'kb'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    embedding_model = Column(String, default="")  # 默认嵌入模型
    top_k = Column(Integer, default=5)  # 默认返回的top_k数量
    files = relationship("File", back_populates="knowledge_base")

class File(Base):
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey('kb.id'))
    file_name = Column(String)
    path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    file_type = Column(String)
    status = Column(Integer, default=0)  # 0: 未处理, 1: 处理中, 2: 已处理, 3: 错误
    knowledge_base = relationship("KnowledgeBase", back_populates="files")
    chunks = relationship("Chunk", back_populates="file")

class Chunk(Base):
    __tablename__ = 'chunks'
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey('file.id'))
    text = Column(Text)

    file = relationship("File", back_populates="chunks")
    vector = relationship("Vector", uselist=False, back_populates="chunk") # One-to-one

class Vector(Base):
    __tablename__ = 'vectors'
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey('chunks.id'), unique=True)
    embedding = Column(LargeBinary) # Store embeddings as binary

    chunk = relationship("Chunk", back_populates="vector")

# 数据库连接
DATABASE_URL = "sqlite:///./knowledge_base.db" # 生产环境请更换为 PostgreSQL/MySQL
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建所有表 (可以在应用启动时执行一次)
def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
    print("Database tables created/checked.")

# 定义嵌入维度（请根据你实际使用的模型调整）
EMBEDDING_DIM = 1024