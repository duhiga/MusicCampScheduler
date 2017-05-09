from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class

class location(Base):
    __tablename__ = 'locations'

    locationid = Column(Integer, primary_key=True, unique=True)
    locationname = Column(String)
    capacity = Column(Integer, default='0')
    autoallocate = Column(Integer, default='1')

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns true if the location is free during this period, optionally ignoring the input group
    def isfree(self,session,thisperiod,thisgroup=None):
        isfreequery = session.query(group).filter(group.periodid == thisperiod.periodid, group.locationid == self.locationid)
        if thisgroup is not None:
            isfreequery = isfreequery.filter(group.groupid != thisgroup.groupid)
        if isfreequery.first() is None:
            return True
        else:
            return False