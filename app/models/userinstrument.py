from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from app.models import serialize_class

class userinstrument(Base):
    __tablename__ = 'userinstruments'

    userinstrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    instrumentid = Column(Integer, ForeignKey('instruments.instrumentid'))
    level = Column(Integer)
    isprimary = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)