from sqlalchemy import *
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

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

    #adds this user to a group. The group object passed in must have at least a groupid and periodid
    def addtogroup(self, session, thisgroup, instrumentname=None):
        #check if this user plays this instrument (if an instrument was specified)
        if instrumentname is not None and session.query(instrument).filter(instrument.userid == self.userid, instrument.instrumentname == instrumentname).first() is None:
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,instrumentname,thisgroup.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (self.firstname,self.lastname,instrumentname,thisgroup.groupid))
        #if the user is already in this group, don't add another groupassignment, just log it
        if session.query(groupassignment).filter(groupassignment.userid == self.userid, groupassignment.groupid == thisgroup.groupid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already in group %s. Made no changes to this player.' % (self.firstname,self.lastname,group.groupid))
        #if the user is already playing in another group at this time, raise an exception
        elif thisgroup.periodid is not None and session.query(groupassignment).join(group).filter(groupassignment.userid == self.userid, group.periodid == thisgroup.periodid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (self.firstname,self.lastname))
        else:
            playergroupassignment = groupassignment(userid = self.userid, groupid = thisgroup.groupid, instrumentname = instrumentname)
            session.add(playergroupassignment)

    #marking a user absent for a period simply assigns them to a group called "absent" during that period
    def markabsent(self,session,thisperiod):
        absentgroup = session.query(group.groupid).join(period).filter(group.groupname == 'absent', period.periodid == thisperiod.periodid).first()
        self.addtogroup(session,absentgroup)

    #marking a user present searches for an absent listing for them, and removes it
    def markpresent(self,session,thisperiod):
        absentassignment = session.query(groupassignment).join(group).filter(group.groupname == 'absent', group.periodid == thisperiod.periodid, groupassignment.userid == self.userid).first()
        if absentassignment is not None:
            session.delete(absentassignment)