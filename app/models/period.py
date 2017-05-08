from sqlalchemy import *
from .base import Base

class period(Base):
    __tablename__ = 'periods'

    periodid = Column(Integer, primary_key=True, unique=True)
    starttime = Column(DateTime)
    endtime = Column(DateTime)
    periodname = Column(String)
    meal = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)