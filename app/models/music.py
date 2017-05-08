from sqlalchemy import *
from sqlalchemy.orm import relationship
from .base import Base

class music(Base):
    __tablename__ = 'musics'

    musicid = Column(Integer, primary_key=True, unique=True)
    composer = Column(Text(convert_unicode=True))
    musicname = Column(Text(convert_unicode=True))
    source = Column(Text(convert_unicode=True))
    notes = Column(Text(convert_unicode=True))
    link = Column(Text(convert_unicode=True))
    grouptemplateid = Column(Integer, ForeignKey('grouptemplates.grouptemplateid'))
    
    @property
    def serialize(self):
        return serialize_class(self, self.__class__)