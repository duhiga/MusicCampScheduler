from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from app.models import serialize_class, instrument, groupassignment, group, period, userinstrument, getperiod
from app.config import *

class user(Base):
    __tablename__ = 'users'

    userid = Column(UUID, primary_key=True, unique=True)
    logonid = Column(UUID, unique=True)
    firstname = Column(String)
    lastname = Column(String)
    email = Column(String)
    arrival = Column(DateTime)
    departure = Column(DateTime)
    grouprequestcount = Column(Integer)
    isannouncer = Column(Integer)
    isconductor = Column(Integer)
    isadmin = Column(Integer)
    isactive = Column(Integer)

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    def playsinstrument(self, session, thisinstrument):
        if session.query(userinstrument
                    ).filter(userinstrument.userid == self.userid, 
                        instrument.instrumentid == thisinstrument.instrumentid
                    ).first() is not None:
            return True
        else:
            return False

    def isplayingingroup(self, session, thisgroup):
        if session.query(groupassignment
                    ).filter(groupassignment.userid == self.userid, 
                        groupassignment.groupid == thisgroup.groupid
                    ).first() is not None:
            return True
        else:
            return False

    def isplayinginperiod(self, session, thisperiod):
        if thisperiod.periodid is not None and session.query(groupassignment
                    ).join(group
                    ).filter(groupassignment.userid == self.userid, 
                        group.periodid == thisperiod.periodid
                    ).first() is not None:
            return True
        else:
            return False

    #adds this user to a group. The group object passed in must have at least a groupid and periodid
    def addtogroup(self,session,thisgroup,thisinstrument=None):
        #check if this user plays this instrument (if an instrument was specified)
        if thisinstrument is not None and not self.playsinstrument(session, thisinstrument):
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,thisinstrument.instrumentname,thisgroup.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,thisinstrument.instrumentname,thisgroup.groupid))
        #if the user is already in this group, don't add another groupassignment, just log it
        if self.isplayingingroup(session,thisgroup):
            log('ADDPLAYER: Found that player %s %s is already in group %s. Made no changes to this player.' % (self.firstname,self.lastname,thisgroup.groupid))
        #if the user is already playing in another group at this time, raise an exception
        if thisgroup.periodid is not None and self.isplapyinginperiod(session, getperiod(session,thisgroup.periodid)):
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
        else:
            playergroupassignment = groupassignment(userid = self.userid, 
                        groupid = thisgroup.groupid, 
                        instrumentid = thisinstrument.instrumentid)
            session.add(playergroupassignment)
            return True

    #marking a user absent for a period simply assigns them to a group called "absent" during that period
    def markabsent(self,session,thisperiod):
        absentgroup = session.query(group.groupid
                    ).join(period
                    ).filter(group.groupname == 'absent', 
                        period.periodid == thisperiod.periodid
                    ).first()
        self.addtogroup(session,absentgroup)

    #marking a user present searches for an absent listing for them, and removes it
    def markpresent(self,session,thisperiod):
        absentassignment = session.query(groupassignment
                    ).join(group
                    ).filter(group.groupname == 'absent', 
                        group.periodid == thisperiod.periodid, 
                        groupassignment.userid == self.userid
                    ).first()
        if absentassignment is not None:
            session.delete(absentassignment)

    #Looks up the amount of times a user has participated in an "ismusical" group during the camp
    def playcount(self, session):
        return session.query(user.userid
                    ).join(groupassignment, user.userid == groupassignment.userid
                    ).join(group, groupassignment.groupid == group.groupid
                    ).outerjoin(period
                    ).filter(user.userid == self.userid, 
                            group.ismusical == 1, 
                            period.endtime <= now()
                    ).count()
    
    def getinstruments(self, session):
        return session.query(userinstrument
                    ).join(user
                    ).filter(user.userid == self.userid
                    ).all()