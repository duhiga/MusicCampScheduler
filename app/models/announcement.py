from sqlalchemy import *
from .base import Base

class announcement(Base):
    __tablename__ = 'announcements'

    announcementid = Column(Integer, primary_key=True, unique=True)
    creationtime = Column(DateTime)
    content = Column(Text(convert_unicode=True))