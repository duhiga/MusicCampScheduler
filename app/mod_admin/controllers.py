import smtplib
from flask import Blueprint, render_template, request
import sqlalchemy
from sqlalchemy import *
from app import Session
from app.models import *

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

def send_email(recipient, subject, body):
    print('Email send requested for user %s' % recipient)
    FROM = getconfig('Name')
    TO = recipient if type(recipient) is list else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        # SMTP_SSL code:
        server_ssl = smtplib.SMTP_SSL(getconfig('SMTP_Server'), 465)
        server_ssl.ehlo() # optional, called by login()
        server_ssl.login(getconfig('SMTP_User'), getconfig('SMTP_Password'))  
        # ssl server doesn't support or need tls, so don't call server_ssl.starttls() 
        server_ssl.sendmail(FROM, TO, message)
        #server_ssl.quit()
        server_ssl.close()

        # Non-SSL code:
        #server = smtplib.SMTP(getconfig('SMTP_Server'), 587)
        #server.ehlo()
        #server.starttls()
        #server.login(getconfig('SMTP_User'), getconfig('SMTP_Password'))
        #server.sendmail(FROM, TO, message)
        #server.close()

        print ('Successfully sent email to %s' % recipient)
        return 'Successfully Sent Email'
    except Exception as ex:
        print ('Failed to send email to %s. Full error: %s' % (recipient, ex))
        return 'Failed to Send Email'