
import subprocess
import sys
from optparse import OptionParser
import ConfigParser
import datetime

import smtplib
from email.mime.text import MIMEText

PARSER = OptionParser(usage="%prog filename", description="""
This script takes as input a URL and checks with wget if 
it can be accessed.
""")

PARSER.add_option("-u", "--url", action="store", type="string", dest="URL", help="URL to try to retrieve (Required)")
PARSER.add_option("-v", "--verbose", action="store_true", dest="VERBOSE", help="Print debug messages")
PARSER.add_option("-f", "--from", action="store", type="string", dest="FROM", help="from email address")
PARSER.add_option("-t", "--to", action="store", type="string", dest="TO", help="to email address - If specified an email will be sent to this address if the site is down")
PARSER.add_option("-c", "--config", action="store", type="string", dest="CONFIGFILE", default="alive.cfg", help="The configuration file")
(OPTIONS, ARGS) = PARSER.parse_args()

if not OPTIONS.URL:
    PARSER.print_help()
    sys.exit(1)

CONFIG = ConfigParser.RawConfigParser()
CONFIG.read( OPTIONS.CONFIGFILE )
if not CONFIG.has_section( OPTIONS.URL ):
    CONFIG.add_section( OPTIONS.URL )

try:
    PREV_STATUS = CONFIG.getboolean( OPTIONS.URL, "Down" )
except:
    PREV_STATUS = False

wget = subprocess.Popen( args=["wget", "--quiet", "--timeout=20", "--tries=3", "--spider", OPTIONS.URL] )

def write( text ):
    if OPTIONS.VERBOSE: print text

if wget.wait():
    write( "%s Down" % OPTIONS.URL)

    if PREV_STATUS:
        write( "State already known" )

    CONFIG.set( OPTIONS.URL, "Down", "yes" )

    if not PREV_STATUS and OPTIONS.TO:
        write( "Mailing...")
        msg = MIMEText("Site is down at %s" % datetime.datetime.now().ctime() )
        msg['Subject'] = "%s Down" % OPTIONS.URL
        if OPTIONS.FROM:
            msg['From'] = OPTIONS.FROM
        msg['To'] = OPTIONS.TO
        s = smtplib.SMTP()
        if OPTIONS.VERBOSE:
            s.set_debuglevel(True)
        s.connect()
        s.sendmail(OPTIONS.FROM, [OPTIONS.TO], msg.as_string())
        s.quit()
else:
    write( "%s Up" % OPTIONS.URL)
    CONFIG.set( OPTIONS.URL, "Down", "no" )

# Write the configuration file
with open('test.cfg', 'wb') as configfile:
    CONFIG.write(configfile)
