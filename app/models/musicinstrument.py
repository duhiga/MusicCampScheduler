from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from .base import Base
from app.models import serialize_class

class musicinstrument(Base):
    __tablename__ = 'musicinstruments'

    musicinstrumentid = Column(Integer, primary_key=True, unique=True)
    musicid = Column(Integer, ForeignKey('musics.musicid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)