import smtplib
import config
from config import *

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