from sqlalchemy import *
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class groupassignment(Base):
    __tablename__ = 'groupassignments'

    groupassignmentid = Column(Integer, primary_key=True, unique=True)
    userid = Column(UUID, ForeignKey('users.userid'))
    groupid = Column(Integer, ForeignKey('groups.groupid'))
    instrumentname = Column(String)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)