from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from .base import Base
from app.models import serialize_class, converttoplayer, player

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

    def getfreelocations(self, session):
        locations_used_query = session.query(location.locationid
                    ).join(group
                    ).join(period
                    ).filter(self.periodid == periodid)
        return session.query(location
                    ).filter(~location.locationid.in_(locations_used_query)
                    ).all()

    def getfreemusics(self, session):
        musics_used_query = session.query(music.musicid
                    ).join(group
                    ).join(period
                    ).filter(self.periodid == periodid)
        return session.query(music
                    ).filter(~music.musicid.in_(musics_used_query)
                    ).all()

    def getfreeconductors(self, session):
        everyone_playing_in_periodquery = session.query(user.userid
                    ).join(groupassignment
                    ).join(group
                    ).join(period
                    ).filter(self.periodid == thisperiod.periodid)
        return session.query(user
                    ).join(userinstrument, user.userid == userinstrument.userid
                    ).join(instrument, userinstrument.instrumentid == instrument.instrumentid
                    ).filter(instrument.instrumentname == 'Conductor', 
                        userinstrument.isactive == 1,
                        ~user.userid.in_(everyone_playing_in_periodquery)
                    ).all()
                    
    def getfreeplayers(self, session):
        everyone_playing_in_periodquery = session.query(user.userid
                    ).join(groupassignment
                    ).join(group
                    ).join(period
                    ).filter(self.periodid == thisperiod.periodid)
        playersdump = session.query(user.userid,
                        user.firstname,
                        user.lastname,
                        instrument.instrumentid,
                        instrument.instrumentname,
                        userinstrument.level,
                        userinstrument.isprimary
                    ).join(userinstrument
                    ).join(instrument
                    ).filter(user.isactive == 1, 
                        userinstrument.isactive == 1,
                        ~user.userid.in_(playersPlayingInPeriod),
                        user.arrival <= thisperiod.starttime, 
                        user.departure >= thisperiod.endtime
                    ).all()
        players = []
        for p in playersdump:
            players.append(converttoplayer(p))
        return players