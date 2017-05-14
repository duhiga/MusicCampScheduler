from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import datetime
from .base import Base
from app.models import serialize_class
from app.config import now

class grouplog(Base):
    __tablename__ = 'grouplogs'

    logid = Column(Integer, primary_key=True, unique=True)
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    timestamp = Column(DateTime, default=now())
    message = Column(Text(convert_unicode=True))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)