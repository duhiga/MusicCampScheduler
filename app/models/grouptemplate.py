from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from .base import Base
from app.models import serialize_class

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    defaultminimumlevel = Column(Integer)
    delautmaximumlevel = Column(Integer)
    defaultlocationid = Column(Integer, ForeignKey('locations.locationid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)