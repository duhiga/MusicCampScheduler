from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, exists, Enum, types, UniqueConstraint, ForeignKeyConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from app.models import serialize_class

class group(Base):
    __tablename__ = 'groups'

    groupid = Column(Integer, primary_key=True, unique=True)
    groupname = Column(String)
    groupdescription = Column(String)
    locationid = Column(Integer, ForeignKey('locations.locationid'))
    requesttime = Column(DateTime)
    requesteduserid = Column(UUID, ForeignKey('users.userid'))
    periodid = Column(Integer, ForeignKey('periods.periodid'))
    minimumlevel = Column(Integer, default='0')
    maximumlevel = Column(Integer, default='0')
    musicid = Column(Integer, ForeignKey('musics.musicid',ondelete='SET NULL'), nullable=True)
    musicwritein = Column(String)
    ismusical = Column(Integer, default='0')
    iseveryone = Column(Integer, default='0')
    status = Column(String)
    log = Column(Text(convert_unicode=True))

    @property
    def serialize(self):
        return serialize_class(self, self.__class__)

    #returns the total number of players that are needed for this group
    @property
    def totalinstrumentation(self):
        total = 0
        for i in getconfig('Instruments').split(","):
            total = total + int(getattr(self,i))
        return int(total)

    #returns a total number of players currently assigned to this group
    @property
    def totalallocatedplayers(self):
        s = Session()
        total = s.query(groupassignment).filter(groupassignment.groupid == self.groupid).count()
        s.close()
        return total

    #returns an array of instrument names that are contained in this group
    @property
    def instruments(self):
        instrumentation = []
        for i in getconfig('Instruments').split(","):
            if getattr(self,i) > 0:
                instrumentation.append(i)
        return instrumentation

    def addtolog(self,text):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') #get the time now and convert it to a string format
        if self.log is None or self.log == '':
            self.log = now + ';' + text
        else:
            self.log = self.log + ',' + now + ';' + text

    #this function obtains the min level, depending on if it's explicitly set, or has players already assigned
    def getminlevel(self,session):
        log('GETMINLEVEL: Finding group minimum level')
        #if the group is set to "auto", i.e. blank or 0, find the minimum level of all the players currently playing in the group
        if self.minimumlevel is None or self.minimumlevel == '' or self.minimumlevel == '0' or self.minimumlevel == 0:
            minimumlevelob = session.query(user.firstname, user.lastname, instrument.instrumentname, instrument.level).join(groupassignment).join(group).\
                join(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)).\
                filter(group.groupid == self.groupid).order_by(instrument.level).first()
            #if we find at least one player in this group, set the minimumlevel to be this players level minus the autoassignlimitlow
            if minimumlevelob is not None:
                log('GETMINLEVEL: Found minimum level in group %s to be %s %s playing %s with level %s' % (self.groupid, minimumlevelob.firstname, minimumlevelob.lastname, minimumlevelob.instrumentname, minimumlevelob.level))
                level = int(minimumlevelob.level) - int(getconfig('AutoAssignLimitLow'))
                if level < 1:
                    level = 1
            #if we don't find a player in this group, set the minimum level to be 0 (not allowed to autofill)
            else: 
                level = 0
        #if this group's minimum level is explicitly set, use that setting
        else:
            level = self.minimumlevel
        log('GETMINLEVEL: Found minimum level of group %s to be %s' % (self.groupid,level))
        return int(level)

    #this function obtains the max level, depending on if it's explicitly set, or has players already assigned
    def getmaxlevel(self,session):
        log('GETMINLEVEL: Finding group minimum level')
        #if the group is set to "auto", i.e. blank or 0, find the maximum level of all the players currently playing in the group
        if self.maximumlevel is None or self.maximumlevel == '' or self.maximumlevel == '0' or self.maximumlevel == 0:
            minimumlevelob = session.query(user.firstname, user.lastname, instrument.instrumentname, instrument.level).join(groupassignment).join(group).\
                join(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)).\
                filter(group.groupid == self.groupid).order_by(instrument.level).first()
            #if we find at least one player in this group, set the maximumlevel to be this players level plus the autoassignlimithigh
            if minimumlevelob is not None:
                log('GETMAXLEVEL: Found minimum level in group %s to be %s %s playing %s with level %s' % (self.groupid, minimumlevelob.firstname, minimumlevelob.lastname, minimumlevelob.instrumentname, minimumlevelob.level))
                level = int(minimumlevelob.level) + int(getconfig('AutoAssignLimitHigh'))
                if level > int(getconfig('AutoAssignLimitHigh')):
                    level = getconfig('MaximumLevel')
            #if we don't find a player in this group, set the maximum level to 0 (not allowed to autofill)
            else:
                level = 0
        #if this group's maximum level is explicitly set, use that setting
        else:
            level = self.maximumlevel
        log('GETMAXLEVEL: Found maximum level of group %s to be %s' % (self.groupid,level))
        return int(level)

    #deletes the group
    def delete(self, session):
        thisgroupassignments = session.query(groupassignment).filter(groupassignment.groupid == self.groupid).all()
        for a in thisgroupassignments:
            session.delete(a)
        session.commit()
        session.delete(self)
        session.commit()

    #get groupassignment listings for all players in this group
    def getplayers(self,session):
        return session.query(groupassignment).filter(groupassignment.groupid == thisgroup.groupid).all()

    #checks if the group can be confirmed, and confirms the group
    def confirm(self, session):
        log('CONFIRMGROUP: Attempting to confirm group name:%s id:%s' % (self.groupname,self.groupid))
        if self.locationid is None:
            raise Exception('Failed to confirm group %s becasue the group is missing a locationid' % self.groupname)
        elif self.periodid is None:
            raise Exception('Failed to confirm group %s becasue the group is missing a periodid' % self.groupname)
        elif self.groupname is None or self.groupname == '':
            raise Exception('Failed to confirm group becasue the group is missing a groupname')
        elif session.query(group).filter(group.periodid == self.periodid, group.locationid == self.locationid, group.groupid != self.groupid).first() is not None:
            raise Exception('Failed to confirm group %s becasue the group location is already in use by another group at this time' % self.groupname)
        elif self.musicid is not None and session.query(group).filter(group.musicid == self.musicid, group.periodid == self.periodid, group.groupid != self.groupid).first() is not None:
            raise Exception('Failed to confirm group %s because the group music is already in use by another group at this time' % self.groupname)

        #check if any players are playing in other groups
        if self.checkplayerclash:
            raise Exception('Failed to confirm group becasue at least one player is in another group at this time.')
        else:
            log('CONFIRMGROUP: Successfully confirmed group name:%s id:%s' % (self.groupname,self.groupid))
            self.status = 'Confirmed'
            
    #adds a single player to this group. The object passed in needs to have at least a userid
    def addplayer(self,session,player,instrumentname):
        #check if this user plays this instrument
        if session.query(instrument).filter(instrument.userid == player.userid, instrument.instrumentname == instrumentname).first() is None:
            log('ADDPLAYER: Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
            raise Exception('Found that player %s %s does not play instrument %s, cannot assign them to group %s' % (player.firstname,player.lastname,instrumentname,self.groupid))
        #if the player is already in this group, don't make another groupassignment, just log it.
        if session.query(groupassignment).filter(groupassignment.userid == player.userid, groupassignment.groupid == self.groupid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already in this group. Made no changes to this player.' % (player.firstname,player.lastname))
        #if the player is in another group at this time, raise an exception
        elif self.periodid is not None and session.query(groupassignment).join(group).filter(groupassignment.userid == player.userid, group.periodid == self.periodid).first() is not None:
            log('ADDPLAYER: Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
            raise Exception('Found that player %s %s is already assigned to a group during this period.' % (player.firstname,player.lastname))
        #otherwise, create a groupassignment for them
        else:
            log('ADDPLAYER: Adding player %s %s to group playing instrument %s' % (player.firstname,player.lastname,instrumentname))
            playergroupassignment = groupassignment(userid = player.userid, groupid = self.groupid, instrumentname = instrumentname)
            session.add(playergroupassignment)

    #checks if this group can fit into a given period or not (checks player clashes with other groups)
    def checkplayerclash(self,session,selectedperiod):
        playersPlayingInPeriod = session.query(groupassignment.userid).join(group).filter(group.groupid != self.groupid).filter(group.periodid == selectedperiod.periodid)
        if session.query(groupassignment.userid).filter(groupassignment.groupid == self.groupid, groupassignment.userid.in_(playersPlayingInPeriod)).first() is not None:
            log('CHECKPLAYERCLASH: Found a player clash for group with id:%s and period id:%s' % (self.groupid,selectedperiod.periodid))
            return True
        else:
            log('CHECKPLAYERCLASH: Found that group id:%s can fit into period id:%s' % (self.groupid,selectedperiod.periodid))
            return False

    #adds a list of players to this group. The list must contain at least userids. Does not commit the group.
    def addplayers(self,session,playerlist):
        try:
            log('ADDPLAYERS: Adding a list of players to group name:%s id:%s' % (self.groupname, self.groupid))
            for player in playerlist:
                self.addplayer(session,player,player.instrumentname)
            log('ADDPLAYERS: Finished adding players to group')
        except Exception as ex:
            raise Exception(ex)

    def purgeoldplayers(self,session):
        log('GROUPPURGE: Purging old players from group name:%s id:%s' % (self.groupname,self.groupid))
        oldplayers = session.query(groupassignment
                        ).join(user
                        ).filter(
                            groupassignment.groupid == self.groupid,
                            user.departure < datetime.datetime.now(),
                            user.isactive != 1
                        ).all()
        for p in oldplayers:
            session.delete(p)
        return False