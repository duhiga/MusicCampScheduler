from sqlalchemy import *
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class instrument(Base):
    __tablename__ = 'instruments'

    instrumentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    instrumentname = Column(String)
    level = Column(Integer)
    isprimary = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)