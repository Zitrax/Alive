"""
This script takes as input a URL and checks with wget if it can be accessed.
"""

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

        CONFIG.set( URL, "Down", "yes" )

        if not PREV_STATUS and OPTIONS.TO:
            write( "Mailing...")
            MSG = MIMEText("Site is down at %s" % datetime.datetime.now().ctime() )
            MSG['Subject'] = "%s Down" % URL
            if OPTIONS.FROM:
                MSG['From'] = OPTIONS.FROM
            MSG['To'] = OPTIONS.TO
            S = smtplib.SMTP()
            if OPTIONS.VERBOSE:
                S.set_debuglevel(True)
            S.connect()
            S.sendmail(OPTIONS.FROM, [OPTIONS.TO], MSG.as_string())
            S.quit()
    else:
        write( "Up\n" )
        CONFIG.set( URL, "Down", "no" )

# Write the configuration file
with open( OPTIONS.CONFIGFILE, 'wb') as configfile:
    CONFIG.write(configfile)
