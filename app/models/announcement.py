from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class

class announcement(Base):
    __tablename__ = 'announcements'

    announcementid = Column(Integer, primary_key=True, unique=True)
    creationtime = Column(DateTime)
    content = Column(Text(convert_unicode=True))