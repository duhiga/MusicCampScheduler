from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from .base import Base
from app.models import serialize_class

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    instrumentname = Column(Text(convert_unicode=True))
    order = Column(Integer, unique=True)
    abbreviations = Column(ARRAY(String))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)