import sqlalchemy
import os
from datetime import date, timedelta
from .DBSetup import *
from sqlalchemy import *
from sqlalchemy.orm import aliased
from .config import *
from .SMTPemail import *

# Looks up the amount of times a user has participated in an "ismusical" group during the camp


def playcount(session, userid):
    playcount = session.query(user.userid).join(groupassignment, user.userid == groupassignment.userid).join(group, groupassignment.groupid == group.groupid).outerjoin(
        period).filter(user.userid == userid, group.ismusical == 1, period.endtime <= datetime.datetime.now()).count()
    return playcount

# get the information needed to fill in the user's schedule table


def getschedule(session, thisuser, date):
    # find the start of the next day
    nextday = date + datetime.timedelta(days=1)

    schedule = []
    # for each period in the requested day
    for p in session.query(period).filter(period.starttime > date, period.endtime < nextday).order_by(period.starttime).all():
        # try to find a group assignment for the user
        g = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical, group.iseveryone, music.musicid,
                          period.periodid, period.periodname, groupassignment.instrumentname, period.meal, group.groupdescription, music.composer, music.musicname, group.musicwritein, group.status).\
            join(period).join(groupassignment).join(user).outerjoin(instrument).outerjoin(location).outerjoin(music).\
            filter(user.userid == thisuser.userid, group.periodid == p.periodid, group.status == "Confirmed").first()
        if g is not None:
            schedule.append(g)
        e = None
        # if we didn't find an assigned group...
        if g is None:
            # try to find an iseveryone group at the time of this period
            e = session.query(group.groupname, period.starttime, period.endtime, location.locationname, group.groupid, group.ismusical,
                              group.iseveryone, period.periodid, period.periodname, period.meal, group.groupdescription).\
                join(period).join(location).\
                filter(group.iseveryone == 1,
                       group.periodid == p.periodid).first()
        if e is not None:
            schedule.append(e)
        # if we didn't find an assigned group or an iseveryone group...
        if e is None and g is None:
            # just add the period detalis
            schedule.append(p)
    return schedule


def getgroupname(session, thisgroup):
    debuglog('GETGROUPNAME: Generating a name for requested group')
    instrumentlist = getconfig('Instruments').split(",")

    # if this group's instrumentation matches a grouptempplate, then give it the name of that template
    templatematch = session.query(grouptemplate).filter(
        *[getattr(grouptemplate, i) == getattr(thisgroup, i) for i in instrumentlist]).first()
    if templatematch is not None:
        debuglog('GETGROUPNAME: Found that this group instrumentation matches the template %s' %
                 templatematch.grouptemplatename)
        name = templatematch.grouptemplatename

    # if we don't get a match, then we find how many players there are in this group, and give it a more generic name
    else:
        count = 0
        for i in instrumentlist:
            value = getattr(thisgroup, i)
            debuglog('GETGROUPNAME: Instrument %s is value %s' % (i, value))
            if value is not None:
                count = count + int(getattr(thisgroup, i))
        debuglog('GETGROUPNAME: Found %s instruments in group.' % value)
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
        debuglog('GETGROUPNAME: Found that this groups musicid is %s' %
                 thisgroup.musicid)
        composer = session.query(music).filter(
            music.musicid == thisgroup.musicid).first().composer
        debuglog(
            'GETGROUPNAME: Found composer matching this music to be %s' % composer)
        name = composer + ' ' + name

    debuglog('GETGROUPNAME: Full name of group returned is %s' % name)
    return name

# iterates through the empty slots in a group and finds players to potentially fill them. returns a list of players.


def autofill(session, thisgroup, thisperiod, primary_only=0):
    # get the minimum level of this group
    minlevel = thisgroup.getminlevel(session)
    maxlevel = thisgroup.getmaxlevel(session)
    if minlevel == 0 or maxlevel == 0:
        raise NameError(
            'You cannot autofill with all empty players and an auto minimum or maximum level. Set the level or pick at least one player.')
    final_list = []
    for i in getconfig('Instruments').split(","):
        if int(getattr(thisgroup, i)) > 0:
            debuglog('AUTOFILL: Group has configured %s total players for instrument %s' % (
                getattr(thisgroup, i), i))
            currentinstrumentplayers = session.query(user).join(groupassignment).filter(
                groupassignment.groupid == thisgroup.groupid, groupassignment.instrumentname == i).all()
            requiredplayers = int(getattr(thisgroup, i)) - \
                len(currentinstrumentplayers)
            debuglog('AUTOFILL: Found %s current players for instrument %s' %
                     (len(currentinstrumentplayers), i))
            debuglog('AUTOFILL: We need to autofill %s extra players for instrument %s' % (
                requiredplayers, i))
            if requiredplayers > 0:
                # get the userids of everyone that's already playing in something this period
                everyone_playing_in_period_query = session.query(
                    user.userid.label(
                        'everyone_playing_in_period_query_userid')
                ).join(groupassignment
                       ).join(group
                              ).join(period
                                     ).filter(
                    period.periodid == thisperiod.periodid
                )

                # combine the last query with another query, finding everyone that both plays an instrument that's found in thisgroup AND isn't in the list of users that are already playing in this period.
                # The admin controls if the query allows non-primary instruments by the primary_only dropdown on their UI
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

                debuglog('AUTOFILL: Found %s possible players of a requested %s for instrument %s.' % (
                    len(possible_players_query.all()), requiredplayers, i))
                # if we found at least one possible player
                if len(possible_players_query.all()) > 0:

                    # make a query that totals the nmber of times each potential user has played at camp.
                    playcounts_subquery = session.query(
                        user.userid.label('playcounts_userid'),
                        func.count(user.userid).label("playcount")
                    ).group_by(
                        user.userid
                    ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                ).outerjoin(group, group.groupid == groupassignment.groupid
                                            ).outerjoin(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)
                                                        ).filter(
                        user.userid.in_(possible_players_query),
                        groupassignment.instrumentname != 'Conductor',
                        group.ismusical == 1,
                        group.periodid != None,
                        group.groupid != thisgroup.groupid,
                        # if we are autofilling primary instruments, only include playcount of primaries
                        instrument.isprimary >= int(primary_only)
                    ).subquery()

                    # if this group has assigned music
                    if thisgroup.musicid is not None:
                        # get a count of the amount of times that each potential player has played in this group
                        musiccounts_subquery = session.query(
                            user.userid.label('musiccounts_userid'),
                            func.count(user.userid).label("musiccount")
                        ).group_by(
                            user.userid
                        ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                    ).outerjoin(group, group.groupid == groupassignment.groupid
                                                ).outerjoin(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)
                                                            ).filter(
                            user.userid.in_(possible_players_query),
                            group.ismusical == 1,
                            group.periodid != None,
                            group.groupid != thisgroup.groupid,
                            instrument.isprimary >= int(primary_only),
                            # grab all groups that share a musicid with this group
                            group.musicid == thisgroup.musicid
                        ).subquery()
                    else:
                        # make a query with all userids, and 0s in the next column so the subsequent queries work (because no users have a playcount for this music)
                        musiccounts_subquery = session.query(
                            user.userid.label('musiccounts_userid'),
                            sqlalchemy.sql.expression.literal_column(
                                "0").label("musiccount")
                        ).filter(
                            user.userid.in_(possible_players_query),
                        ).subquery()

                    # make a query we can use to total up the number of times each user has played in a group like this
                    groupcounts_subquery = session.query(
                        user.userid.label('groupcounts_userid'),
                        func.count(user.userid).label("groupcount")
                    ).group_by(user.userid
                               ).outerjoin(groupassignment, groupassignment.userid == user.userid
                                           ).outerjoin(group, group.groupid == groupassignment.groupid
                                                       ).outerjoin(instrument, and_(groupassignment.instrumentname == instrument.instrumentname, user.userid == instrument.userid)
                                                                   ).filter(
                        user.userid.in_(possible_players_query),
                        groupassignment.instrumentname != 'Conductor',
                        group.ismusical == 1,
                        group.periodid != None,
                        group.groupid != thisgroup.groupid,
                        instrument.isprimary >= int(primary_only),
                        # grab all groups that share a name with this group, or have the same instrumentation of this group
                        or_(
                            group.groupname == thisgroup.groupname,
                            and_(*[getattr(thisgroup, inst) == getattr(group, inst)
                                   for inst in instrumentlist])
                        )
                    ).subquery()

                    # Put it all together!
                    instrument_list = session.query(
                        user.userid,
                        user.firstname,
                        user.lastname,
                        instrument.isprimary,
                        sqlalchemy.sql.expression.literal(
                            i).label("instrumentname"),
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
                        # order by the number of times that the players have played this specific piece of music
                        musiccounts_subquery.c.musiccount.nullsfirst(),
                        # then order by primary instruments
                        instrument.isprimary.desc(),
                        # then order by the number of times that the players have played in a group similar to this in name or instrumentation
                        groupcounts_subquery.c.groupcount.nullsfirst(),
                        # then order by their total playcounts
                        playcounts_subquery.c.playcount.nullsfirst()
                    ).limit(requiredplayers).all()
                    debuglog('AUTOFILL: Players in final list with playcounts:')
                    for pl in instrument_list:
                        debuglog('AUTOFILL: Found %s %s to play %s with totals - isprimary:%s musiccount:%s groupcount:%s playcount:%s ' %
                                 (pl.firstname, pl.lastname, pl.isprimary, pl.isprimary, pl.musiccount, pl.groupcount, pl.playcount))
                        final_list.append(pl)
    debuglog('AUTOFILL: Completed autofill selections')
    return final_list
