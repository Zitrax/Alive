#!/usr/bin/python
"""
This script takes as input a URL and checks with wget if it can be accessed,
with mail notifications when the site goes up or down.
"""

import subprocess
import sys
from optparse import OptionParser
import ConfigParser
import datetime
import time

import smtplib
from email.mime.text import MIMEText

sys.path.append("colorama")
from colorama import Fore

def parse_command_line_options():
    """Will parse all options given on the command line and exit if required arguments are not given"""

    global OPTIONS

    parser = OptionParser(usage="%prog [options]", description=
    """This script takes as input one or several URLs and checks with wget if
    they can be accessed.
    """)

    parser.add_option("-u", "--url", dest="URL", help="URL(s) to try to retrieve. You can write several URLs separated by space, but remember to quote the string.")
    parser.add_option("-q", "--quiet", action="store_true", dest="QUIET", help="Avoid all prints")
    parser.add_option("-d", "--debug", action="store_true", dest="DEBUG", help="Print debug messages")
    parser.add_option("-f", "--from", dest="FROM", help="from email address")
    parser.add_option("-t", "--to", dest="TO", help="to email address - If specified an email will be sent to this address if the site is down")
    parser.add_option("-c", "--config", dest="CONFIGFILE", default="alive.cfg", help="The configuration file. By default this is alive.cfg in the current directory.")
    parser.add_option("-k", "--test-known", dest="KNOWN", action="store_true", help="Test all existing URLs in the cfg file.")
    parser.add_option("-l", "--list", dest="LIST", action="store_true", help="List known URLs in the config file.")

    (OPTIONS, args) = parser.parse_args()

    if not (OPTIONS.URL or OPTIONS.KNOWN or OPTIONS.LIST) or len(args):
        parser.print_help()
        sys.exit(1)

def write( text ):
    """Writes the string only if not in quiet mode"""
    if not OPTIONS.QUIET:
        print text,
        sys.stdout.flush()

def check_urls(config, urls):
    """Will go through the url list and check if they are up"""

    state_pos = 30
    for url in urls:
        if len(url) > state_pos:
            state_pos = len(url)

    for url in urls:

        if not config.has_section( url ):
            config.add_section( url )

        try:
            down_earlier = config.getboolean( url, "Down" )
        except ValueError:
            down_earlier = False
        except ConfigParser.NoOptionError:
            down_earlier = False

        try:
            last_change = config.getint( url, "Time" )
        except ValueError:
            last_change = int(time.time())
            config.set( url, "Time", last_change )
        except ConfigParser.NoOptionError:
            last_change = int(time.time())
            config.set( url, "Time", last_change )

        wget = subprocess.Popen( args=["wget", "--no-check-certificate", "--quiet", "--timeout=20", "--tries=3", "--spider", url] )

        write( "Trying %s... " % url )

        res = wget.wait()

        if res and res != 6:
            report( config, url, True, down_earlier, last_change, state_pos )
        else:
            report( config, url, False, not down_earlier, last_change, state_pos )

def report( config, url, down, known_earlier, last_change, state_pos ):
    """Report the state and eventual change"""

    if down:
        state = "down"
        color = Fore.RED
        space = ""
    else:
        state = "up"
        color = Fore.GREEN
        space = "  "

    write( "%s%s%s%s%s" % (color, space, (state_pos-len(url))*" ", state, Fore.RESET))

    if known_earlier:
        write( " (State already known" )
        if last_change:
            write( "since %s" % time.ctime(last_change) )
        else:
            write( " (State changed" )
        write(")\n")

        if known_earlier:
            if OPTIONS.TO:
                if( not send_mail( "%s %s" % (url, state), "Site is %s at %s" % (state, datetime.datetime.now().ctime()) ) ):
                    return
            config.set( url, "Time", int(time.time()) )

        if down:
            config.set( url, "Down", "yes" )
        else:
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
    if OPTIONS.DEBUG:
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

    if OPTIONS.LIST:
        if len(config.sections()):
            print "Known URLs in the config file '%s':\n" % OPTIONS.CONFIGFILE
            for url in config.sections():
                print url
        else:
            print "No URLs in the config file '%s':" % OPTIONS.CONFIGFILE
        sys.exit(0)

    if OPTIONS.KNOWN:
        urls += config.sections()

    check_urls(config, urls)

    # Write the configuration file
    with open( OPTIONS.CONFIGFILE, 'wb') as configfile:
        config.write(configfile)

if __name__ == "__main__":
    main()
