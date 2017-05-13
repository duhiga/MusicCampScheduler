from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class

#this table controls if instruments are able to be placed into a location, for example - you may only have 
# access to a piano in one room. By default, instruments are enabled even if they aren't in this table
class locationinstrument(Base):
    __tablename__ = 'locationinstruments'

    locationinstrumentid = Column(Integer, primary_key=True, unique=True)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))
    isdisabled = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)