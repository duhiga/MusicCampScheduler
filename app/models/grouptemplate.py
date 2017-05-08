from sqlalchemy import *
from sqlalchemy.orm import relationship
from .base import Base

class grouptemplate(Base):
    __tablename__ = 'grouptemplates'

    grouptemplateid = Column(Integer, primary_key=True, unique=True)
    grouptemplatename = Column(String)
    size = Column(String)
    minimumlevel = Column(Integer)
    maximumlevel = Column(Integer)
    defaultlocationid = Column(Integer, ForeignKey('locations.locationid'))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)