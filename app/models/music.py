from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from .base import Base
from app.models import serialize_class

class music(Base):
    __tablename__ = 'musics'

    musicid = Column(Integer, primary_key=True, unique=True)
    composer = Column(Text(convert_unicode=True))
    musicname = Column(Text(convert_unicode=True))
    source = Column(Text(convert_unicode=True))
    notes = Column(Text(convert_unicode=True))
    link = Column(Text(convert_unicode=True))
    
    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns true if the music is free during this period, optionally ignoring the input group
    def isfree(self,session,thisperiod,thisgroup=None):
        isfreequery = session.query(group).filter(group.periodid == thisperiod.periodid, group.musicid == self.musicid)
        if thisgroup is not None:
            isfreequery = isfreequery.filter(group.groupid != thisgroup.groupid)
        if isfreequery.first() is None:
            return True
        else:
            return False