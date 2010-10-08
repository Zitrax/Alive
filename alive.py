"""
This script takes as input a URL and checks with wget if it can be accessed.
"""

# TODO: Write a main function instead of using globals

import subprocess
import sys
from optparse import OptionParser
import ConfigParser
import datetime

import smtplib
from email.mime.text import MIMEText

PARSER = OptionParser(usage="%prog filename", description="""
This script takes as input one or several URLs and checks with wget if
they can be accessed.
""")

PARSER.add_option("-u", "--url", action="store", type="string", dest="URL", help="URL to try to retrieve (Required) You can write several URLs separated by space, but remember to quote the string.")
PARSER.add_option("-v", "--verbose", action="store_true", dest="VERBOSE", help="Print debug messages")
PARSER.add_option("-f", "--from", action="store", type="string", dest="FROM", help="from email address")
PARSER.add_option("-t", "--to", action="store", type="string", dest="TO", help="to email address - If specified an email will be sent to this address if the site is down")
PARSER.add_option("-c", "--config", action="store", type="string", dest="CONFIGFILE", default="alive.cfg", help="The configuration file")
(OPTIONS, ARGS) = PARSER.parse_args()

if not OPTIONS.URL:
    PARSER.print_help()
    sys.exit(1)

URLS = OPTIONS.URL.split()

CONFIG = ConfigParser.RawConfigParser()
CONFIG.read( OPTIONS.CONFIGFILE )

def write( text ):
    """Writes the string only if verbose mode is enabled"""
    if OPTIONS.VERBOSE:
        print text,
        sys.stdout.flush()

def send_mail(subject, body):
    """Send a mail using smtp server on localhost"""
    write( "Mailing...")
    msg = MIMEText(body)
    msg['Subject'] = subject
    if OPTIONS.FROM:
        msg['From'] = OPTIONS.FROM
    msg['To'] = OPTIONS.TO
    smtp = smtplib.SMTP()
    if OPTIONS.VERBOSE:
        smtp.set_debuglevel(True)
    try:
        smtp.connect()
    except:
        print "Could not send email, do you have an SMTP server running on localhost?"
        return False
    smtp.sendmail(OPTIONS.FROM, [OPTIONS.TO], msg.as_string())
    smtp.quit()
    return True

for URL in URLS:

    if not CONFIG.has_section( URL ):
        CONFIG.add_section( URL )

    try:
        PREV_STATUS = CONFIG.getboolean( URL, "Down" )
    except ValueError:
        PREV_STATUS = False
    except ConfigParser.NoOptionError:
        PREV_STATUS = False

    WGET = subprocess.Popen( args=["wget", "--quiet", "--timeout=20", "--tries=3", "--spider", URL] )

    write( "Trying %s... " % URL )

    if WGET.wait():
        write( "Down\n" )

        if PREV_STATUS:
            write( "State already known" )

        if not PREV_STATUS and OPTIONS.TO:
            if( not send_mail( "%s Down" % URL, "Site is down at %s" % datetime.datetime.now().ctime() ) ):
                continue

        CONFIG.set( URL, "Down", "yes" )

    else:
        write( "Up\n" )

        if PREV_STATUS and OPTIONS.TO:
            if( not send_mail( "%s Up" % URL, "Site is up at %s" % datetime.datetime.now().ctime() ) ):
                continue

        CONFIG.set( URL, "Down", "no" )

# Write the configuration file
with open( OPTIONS.CONFIGFILE, 'wb') as configfile:
    CONFIG.write(configfile)
