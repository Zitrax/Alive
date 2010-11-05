"""
This script takes as input a URL and checks with wget if it can be accessed,
with mail notifications when the site goes up or down.
"""

import subprocess
import sys
from optparse import OptionParser
import ConfigParser
import datetime

import smtplib
from email.mime.text import MIMEText

def parse_command_line_options():
    """Will parse all options given on the command line and exit if required arguments are not given"""

    global OPTIONS

    parser = OptionParser(usage="%prog filename", description=
    """This script takes as input one or several URLs and checks with wget if
    they can be accessed.
    """)

    parser.add_option("-u", "--url", dest="URL", help="URL(s) to try to retrieve. You can write several URLs separated by space, but remember to quote the string.")
    parser.add_option("-v", "--verbose", action="store_true", dest="VERBOSE", help="Print debug messages")
    parser.add_option("-f", "--from", dest="FROM", help="from email address")
    parser.add_option("-t", "--to", dest="TO", help="to email address - If specified an email will be sent to this address if the site is down")
    parser.add_option("-c", "--config", dest="CONFIGFILE", default="alive.cfg", help="The configuration file. By default this is alive.cfg in the current directory.")
    parser.add_option("-k", "--test-known", dest="KNOWN", action="store_true", help="Test all existing URLs in the cfg file.")

    (OPTIONS, args) = parser.parse_args()

    if not (OPTIONS.URL or OPTIONS.KNOWN) or len(args):
        parser.print_help()
        sys.exit(1)

def write( text ):
    """Writes the string only if verbose mode is enabled"""
    if OPTIONS.VERBOSE:
        print text,
        sys.stdout.flush()

def check_urls(config, urls):
    """Will go through the url list and check if they are up"""

    for url in urls:

        if not config.has_section( url ):
            config.add_section( url )

        try:
            down_earlier = config.getboolean( url, "Down" )
        except ValueError:
            down_earlier = False
        except ConfigParser.NoOptionError:
            down_earlier = False

        wget = subprocess.Popen( args=["wget", "--no-check-certificate", "--quiet", "--timeout=20", "--tries=3", "--spider", url] )

        write( "Trying %s... " % url )

        res = wget.wait()

        if res and res != 6:
            write( "Down" )

            if down_earlier:
                write( " (State already known)" )
            write("\n")

            if not down_earlier and OPTIONS.TO:
                if( not send_mail( "%s Down" % url, "Site is down at %s" % datetime.datetime.now().ctime() ) ):
                    continue

            config.set( url, "Down", "yes" )

        else:
            write( "Up" )

            if not down_earlier:
                write( " (State already known)" )
            write("\n")

            if down_earlier and OPTIONS.TO:
                if( not send_mail( "%s Up" % url, "Site is up at %s" % datetime.datetime.now().ctime() ) ):
                    continue

            config.set( url, "Down", "no" )

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

def main():
    """main"""
 
    parse_command_line_options()

    urls = []
    if OPTIONS.URL:
        urls += OPTIONS.URL.split()

    config = ConfigParser.RawConfigParser()
    config.read( OPTIONS.CONFIGFILE )

    if OPTIONS.KNOWN:
        urls += config.sections()

    check_urls(config, urls)

    # Write the configuration file
    with open( OPTIONS.CONFIGFILE, 'wb') as configfile:
        config.write(configfile)

if __name__ == "__main__":
    main()
