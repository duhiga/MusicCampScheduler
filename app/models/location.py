from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer, default='0')
    autoallocate = Column(Integer, default='1')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)