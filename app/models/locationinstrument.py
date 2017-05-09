from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class

#this table controls if instruments are able to be placed into a location, for example - you may only have access to a piano in one room
class locationinstrument(Base):
    __tablename__ = 'locationinstruments'

    locationinstrumentid = Column(Integer, primary_key=True, unique=True)
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))
    isdisabled = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)