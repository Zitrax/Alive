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
import os

import smtplib
from email.mime.text import MIMEText

sys.path.append(os.path.join(os.path.dirname(__file__),"colorama"))
from colorama import Fore

class Alive:
    """
    This class takes as input a URL and checks with wget if it can be accessed,
    with mail notifications when the site goes up or down.
    """

    def __init__(self):
        self.options = None

    def parse_command_line_options(self):
        """Will parse all self.options given on the command line and exit if required arguments are not given"""
    
        parser = OptionParser(usage="%prog [self.options]", description=
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
        parser.add_option("--test", dest="TEST", action="store_true", help="Run unit tests")
    
        (self.options, args) = parser.parse_args()
    
        if not (self.options.TEST or self.options.URL or self.options.KNOWN or self.options.LIST) or len(args):
            parser.print_help()
            return False
        return True
    
    def write(self, text):
        """Writes the string only if not in quiet mode"""
        if not self.options.QUIET:
            print text,
            sys.stdout.flush()
    
    def check_urls(self, config, urls):
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
    
            self.write( "Trying %s... " % url )
    
            res = wget.wait()
    
            if res and res != 6:
                self.report( config, url, True, down_earlier, last_change, state_pos )
            else:
                self.report( config, url, False, not down_earlier, last_change, state_pos )
    
    def report( self, config, url, down, known_earlier, last_change, state_pos ):
        """Report the state and eventual change"""
    
        if down:
            state = "down"
            color = Fore.RED
            space = ""
        else:
            state = "up"
            color = Fore.GREEN
            space = "  "
    
        self.write( "%s%s%s%s%s" % (color, space, (state_pos-len(url))*" ", state, Fore.RESET))
    
        if known_earlier:
            self.write( " ( State already known" )
            if last_change:
                self.write( "since %s" % time.ctime(last_change) )
        else:
            self.write( " ( State changed" )
        self.write(")\n")
    
        if not known_earlier:
            if self.options.TO:
                if( not self.send_mail( "%s %s" % (url, state), "Site is %s at %s" % (state, datetime.datetime.now().ctime()) ) ):
                    return
            config.set( url, "Time", int(time.time()) )
    
        if down:
            config.set( url, "Down", "yes" )
        else:
            config.set( url, "Down", "no" )
    
    def send_mail(self, subject, body):
        """Send a mail using smtp server on localhost"""
        self.write( "Mailing...")
        msg = MIMEText(body)
        msg['Subject'] = subject
        if self.options.FROM:
            msg['From'] = self.options.FROM
        msg['To'] = self.options.TO
        smtp = smtplib.SMTP()
        if self.options.DEBUG:
            smtp.set_debuglevel(True)
        try:
            smtp.connect()
        except:
            print "Could not send email, do you have an SMTP server running on localhost?"
            return False
        smtp.sendmail(self.options.FROM, [self.options.TO], msg.as_string())
        smtp.quit()
        return True
    
    def writeConfig(self, config):
        # Write the configuration file
        with open( self.options.CONFIGFILE, 'wb') as configfile:
            config.write(configfile)
    
    def setup(self):
        """Read in the config file and URLs"""
        urls = []
        if self.options.URL:
            urls += self.options.URL.split()
    
        config = ConfigParser.RawConfigParser()
        config.read( self.options.CONFIGFILE )
    
        if self.options.KNOWN:
            urls += config.sections()
    
        return (config,urls)

import unittest

class TestAlive(unittest.TestCase):    

    def setUp(self):
        self.alive = Alive()
        self.configfile = "unittest_test_config"
        try:
            os.remove(self.configfile)
        except:
            pass
 
    def __del__(self):
        try:
            os.remove(self.configfile)
        except:
            pass        
 
    def test_empty_config(self):
        sys.argv = [sys.argv[0], "-c", self.configfile, "-l"]
        self.alive.parse_command_line_options()
        (config,urls) = self.alive.setup()
        self.assertEqual(len(config.sections()),0)

    def urlTest(self,url,up,count=1):
        sys.argv = [sys.argv[0], "-c", self.configfile, "-q", "-u", url]
        self.alive.parse_command_line_options()
        (config,urls) = self.alive.setup()
        self.alive.check_urls(config, urls)
        self.alive.writeConfig(config)
        (config,urls) = self.alive.setup()
        self.assertEqual(len(config.sections()),count)
        self.assertTrue(config.has_section(url))
        if up:
            self.assertFalse(config.getboolean(url, "Down"))
        else:
            self.assertTrue(config.getboolean(url, "Down"))

    def test_google(self):
        self.urlTest("www.google.com",True)
        
    def test_down(self):
        self.urlTest("www.ifnvernieunviereev.com",False)
        
    def test_two_sites(self):
        self.urlTest("www.ifjirfijfirjfrijfiY.com", False)
        self.urlTest("www.ifjirfijfirjfrijfiX.com", False,2)

    def test_known(self):
        # First just add a url to the config file
        url = "www.google.com"
        self.alive.parse_command_line_options()
        (config,urls) = self.alive.setup()
        config.add_section(url)
        self.alive.writeConfig(config)
        
        # Then lets test the existing urls from the file
        sys.argv = [sys.argv[0], "-c", self.configfile, "-q", "-k"]
        self.alive.parse_command_line_options()
        (config,urls) = self.alive.setup()
        self.alive.check_urls(config, urls)
        self.alive.writeConfig(config)
        (config,urls) = self.alive.setup()
        self.assertEqual(len(config.sections()),1)
        self.assertTrue(config.has_section(url))
        self.assertFalse(config.getboolean(url, "Down"))

    # TODO: Should check the Time value

def main():
    """main"""

    alive = Alive()

    if not alive.parse_command_line_options():
        sys.exit(1)

    if alive.options.TEST:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAlive)
        
        unittest.TextTestRunner(verbosity=2).run(suite)
    else:
        (config,urls) = alive.setup()

        if alive.options.LIST:
            if len(config.sections()):
                print "Known URLs in the config file '%s':\n" % alive.options.CONFIGFILE
                for url in config.sections():
                    print url
            else:
                print "No URLs in the config file '%s'" % alive.options.CONFIGFILE
            return

        alive.check_urls(config, urls)
        alive.writeConfig(config)


if __name__ == "__main__":
    main()
