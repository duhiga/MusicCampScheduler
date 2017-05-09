import sqlalchemy
import os
from datetime import date, timedelta
from DBSetup import *
from sqlalchemy import *
from sqlalchemy.orm import aliased
from config import *
from SMTPemail import *

def getgroupname(session,thisgroup):
    log('GETGROUPNAME: Generating a name for requested group')
    instrumentlist = getconfig('Instruments').split(",")

    #if this group's instrumentation matches a grouptempplate, then give it the name of that template
    templatematch = session.query(grouptemplate).filter(*[getattr(grouptemplate,i) == getattr(thisgroup,i) for i in instrumentlist]).first()
    if templatematch is not None:
        log('GETGROUPNAME: Found that this group instrumentation matches the template %s' % templatematch.grouptemplatename)
        name = templatematch.grouptemplatename

    #if we don't get a match, then we find how many players there are in this group, and give it a more generic name
    else:
        count = 0
        for i in instrumentlist:
            value = getattr(thisgroup, i)
            log('GETGROUPNAME: Instrument %s is value %s' % (i, value))
            if value is not None:
                count = count + int(getattr(thisgroup, i))
        log('GETGROUPNAME: Found %s instruments in group.' % value)
        if count == 1:
            name = 'Solo'
        elif count == 2:
            name = 'Duet'
        elif count == 3:
            name = 'Trio'
        elif count == 4:
            name = 'Quartet'
        elif count == 5:
            name = 'Quintet'
        elif count == 6:
            name = 'Sextet'
        elif count == 7:
            name = 'Septet'
        elif count == 8:
            name = 'Octet'
        elif count == 9:
            name = 'Nonet'
        elif count == 10:
            name = 'Dectet'
        else:
            name = 'Custom Group'

    if thisgroup.musicid is not None:
        log('GETGROUPNAME: Found that this groups musicid is %s' % thisgroup.musicid)
        composer = session.query(music).filter(music.musicid == thisgroup.musicid).first().composer
        log('GETGROUPNAME: Found composer matching this music to be %s' % composer)
        name = composer + ' ' + name
        
    log('GETGROUPNAME: Full name of group returned is %s' % name)
    return name

#iterates through the empty slots in a group and finds players to potentially fill them. returns a list of players.
def autofill(session,thisgroup,thisperiod,primary_only=0):
    #get the minimum level of this group
    minlevel = thisgroup.getminlevel(session)
    maxlevel = thisgroup.getmaxlevel(session)
    if minlevel == 0 or maxlevel == 0:
        raise NameError('You cannot autofill with all empty players and an auto minimum or maximum level. Set the level or pick at least one player.')
    final_list = []
    for i in getconfig('Instruments').split(","):
        if int(getattr(thisgroup,i)) > 0:
            log('AUTOFILL: Group has configured %s total players for instrument %s' % (getattr(thisgroup,i), i))
            currentinstrumentplayers = session.query(user).join(groupassignment).filter(groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).all()
            requiredplayers = int(getattr(thisgroup,i)) - len(currentinstrumentplayers)
            log('AUTOFILL: Found %s current players for instrument %s' % (len(currentinstrumentplayers), i))
            log('AUTOFILL: We need to autofill %s extra players for instrument %s' % (requiredplayers, i))
            if requiredplayers > 0:
                #get the userids of everyone that's already playing in something this period
                everyone_playing_in_period_query = session.query(
                        user.userid.label('everyone_playing_in_period_query_userid')
                    ).join(groupassignment
                    ).join(group
                    ).join(period
                    ).filter(
                        period.periodid == thisperiod.periodid
                    )

                #combine the last query with another query, finding everyone that both plays an instrument that's found in thisgroup AND isn't in the list of users that are already playing in this period.
                #The admin controls if the query allows non-primary instruments by the primary_only dropdown on their UI
                possible_players_query = session.query(
                        user.userid.label('possible_players_query_userid')
                    ).outerjoin(instrument
                    ).filter(
                        ~user.userid.in_(everyone_playing_in_period_query), 
                        user.isactive == 1, 
                        user.arrival <= thisperiod.starttime, 
                        user.departure >= thisperiod.endtime
                    ).filter(
                        instrument.level >= minlevel, 
                        instrument.level <= maxlevel, 
                        instrument.instrumentname == i, 
                        instrument.isactive == 1, 
                        instrument.isprimary >= int(primary_only)
                    )

                log('AUTOFILL: Found %s possible players of a requested %s for instrument %s.' % (len(possible_players_query.all()), requiredplayers, i))
                #if we found at least one possible player
                if len(possible_players_query.all()) > 0:
                    
                    #make a query that totals the nmber of times each potential user has played at camp.
                    playcounts_subquery = session.query(
                            user.userid.label('playcounts_userid'),
                            func.count(user.userid).label("playcount")
                        ).group_by(
                            user.userid
                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                        ).outerjoin(group, group.groupid == groupassignment.groupid
                        ).filter(
                            user.userid.in_(possible_players_query),
                            groupassignment.instrumentname != 'Conductor', 
                            group.ismusical == 1, 
                            group.periodid != None,
                            group.groupid != thisgroup.groupid
                        ).subquery()

                    #if this group has assigned music
                    if thisgroup.musicid is not None:
                        #get a count of the amount of times that each potential player has played in this group
                        musiccounts_subquery = session.query(
                                user.userid.label('musiccounts_userid'),
                                func.count(user.userid).label("musiccount")
                            ).group_by(
                                user.userid
                            ).outerjoin(groupassignment, groupassignment.userid == user.userid
                            ).outerjoin(group, group.groupid == groupassignment.groupid
                            ).filter(
                                user.userid.in_(possible_players_query),
                                group.ismusical == 1,           
                                group.periodid != None,
                                group.groupid != thisgroup.groupid,
                                #grab all groups that share a musicid with this group
                                group.musicid == thisgroup.musicid
                            ).subquery()
                    else:
                        #make a query with all userids, and 0s in the next column so the subsequent queries work (because no users have a playcount for this music)
                        musiccounts_subquery = session.query(
                                user.userid.label('musiccounts_userid'),
                                sqlalchemy.sql.expression.literal_column("0").label("musiccount")
                            ).filter(
                                user.userid.in_(possible_players_query),
                            ).subquery()

                    #make a query we can use to total up the number of times each user has played in a group like this
                    groupcounts_subquery = session.query(
                            user.userid.label('groupcounts_userid'),
                            func.count(user.userid).label("groupcount")
                        ).group_by(
                            user.userid
                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                        ).outerjoin(group, group.groupid == groupassignment.groupid
                        ).filter(
                            user.userid.in_(possible_players_query),
                            groupassignment.instrumentname != 'Conductor', 
                            group.ismusical == 1,           
                            group.periodid != None,
                            group.groupid != thisgroup.groupid,
                            #grab all groups that share a name with this group, or have the same instrumentation of this group
                            or_(
                                group.groupname == thisgroup.groupname,
                                and_(*[getattr(thisgroup,inst) == getattr(group,inst) for inst in instrumentlist])
                            )
                        ).subquery()

                    #Put it all together!
                    instrument_list = session.query(
                            user.userid,
                            user.firstname,
                            user.lastname,
                            instrument.isprimary,
                            sqlalchemy.sql.expression.literal(i).label("instrumentname"),
                            playcounts_subquery.c.playcount,
                            musiccounts_subquery.c.musiccount,
                            groupcounts_subquery.c.groupcount
                        ).join(instrument, instrument.userid == user.userid
                        ).outerjoin(playcounts_subquery, playcounts_subquery.c.playcounts_userid == user.userid
                        ).outerjoin(musiccounts_subquery, musiccounts_subquery.c.musiccounts_userid == user.userid
                        ).outerjoin(groupcounts_subquery, groupcounts_subquery.c.groupcounts_userid == user.userid
                        ).filter(
                            user.userid.in_(possible_players_query),
                            instrument.instrumentname == i
                        ).order_by(
                            #order by the number of times that the players have played this specific piece of music
                            musiccounts_subquery.c.musiccount.nullsfirst(), 
                            #then order by primary instruments
                            instrument.isprimary.desc(),
                            #then order by the number of times that the players have played in a group similar to this in name or instrumentation
                            groupcounts_subquery.c.groupcount.nullsfirst(), 
                            #then order by their total playcounts
                            playcounts_subquery.c.playcount.nullsfirst()
                        ).limit(requiredplayers
                        ).all()
                    log('AUTOFILL: Players in final list with playcounts:')
                    for pl in instrument_list:
                        log('AUTOFILL: Found %s %s to play %s with totals - isprimary:%s musiccount:%s groupcount:%s playcount:%s ' % (pl.firstname, pl.lastname, pl.isprimary, pl.isprimary, pl.musiccount, pl.groupcount, pl.playcount))
                        final_list.append(pl)
    log('AUTOFILL: Completed autofill selections')
    return final_list