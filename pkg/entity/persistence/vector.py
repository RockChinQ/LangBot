from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import numpy as np # 用于处理从LargeBinary转换回来的embedding

Base = declarative_base()

class Vector(Base):
    __tablename__ = 'vectors'
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey('chunks.id'), unique=True)
    embedding = Column(LargeBinary) # Store embeddings as binary

    chunk = relationship("Chunk", back_populates="vector")