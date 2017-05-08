from sqlalchemy import *
from .base import Base

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer, default='0')
    autoallocate = Column(Integer, default='1')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)