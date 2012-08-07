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
import stat
import re
import threading

import smtplib
from email.mime.text import MIMEText

class SiteThread(threading.Thread):
    """Manages one site in a thread"""

    def __init__(self, site):
        threading.Thread.__init__(self)
        self.__site = site

    def run(self):
        self.__site.get_res()

    def get_site(self):
        return self.__site

class Site:
    """Class that handles one site to check"""

    def __init__(self, url, config, alive):
        """We need to pass by reference so pass the config as an array wrapper"""
        self.__url = url
        self.__config = config
        self.__alive = alive
        self.__res = None
        if not config[0].has_section( url ):
            config[0].add_section( url )
            self.__new = True
        else:
            self.__new = False
        try:
            self.__down = config[0].getboolean( url, "Down" )
        except ValueError:
            self.__down = False
        except ConfigParser.NoOptionError:
            self.__down = False
        try:
            self.__last_change = config[0].getint( url, "Time" )
        except ValueError:
            self.__last_change = int(time.time())
            config[0].set( url, "Time", self.__last_change )
        except ConfigParser.NoOptionError:
            self.__last_change = int(time.time())
            config[0].set( url, "Time", self.__last_change )

    def get_last_change(self):
        return self.__last_change

    def set_last_change(self, new_time):
        self.__config[0].set(self.__url, "Time", new_time)
        self.__last_change = new_time

    def get_down(self):
        return self.__down

    def set_down(self, down):
        self.__config[0].set(self.__url, "Down", "yes" if down else "no")
        self.__down = down

    def get_url(self):
        return self.__url

    def get_new(self):
        return self.__new

    def get_config(self):
        return self.__config

    def get_res(self):
        if self.__res is None:
            self.check_alive()
        return self.__res

    def check_alive(self):
        wget_args = ["wget", "--no-check-certificate", "--quiet", "--timeout=20", "--tries=3", "--spider", self.get_url()]
        self.__alive.write_debug("Checking using cmd: '" + ' '.join(wget_args) + "'\n")
        wget = subprocess.Popen( args=wget_args )
        self.__res = wget.wait()

    def activate_triggers(self, down=False):
        """When site switch state it can have some triggers that should be activated"""
        command = ""
        if down and self.__config[0].has_option(self.__url, "down_trigger"):
            command = self.__config[0].get(self.__url, "down_trigger")
        elif not down and self.__config[0].has_option(self.__url, "up_trigger"):
            command = self.__config[0].get(self.__url, "up_trigger")

        if len(command):
            ret = 1
            try:
                ret = subprocess.call( command, shell=True )
            except OSError:
                pass
            if ret:
                self.__alive.write_warn("could not run '%s'\n" % command, Color.YELLOW)

class Color:
    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'
    RESET   = '\033[39m'

class Alive:
    """
    This class takes as input a URL and checks with wget if it can be accessed,
    with mail notifications when the site goes up or down.
    """

    def __init__(self):
        self.options = None

    def parse_command_line_options(self):
        """Will parse all self.options given on the command line and exit if required arguments are not given"""

        parser = OptionParser(usage="%prog [options]", description=
        """This script takes as input one or several URLs and checks with wget if
        they can be accessed.
        """)

        parser.add_option("-u", "--url", dest="URL", help="URL(s) to try to retrieve. You can write several URLs separated by space, but remember to quote the string.")
        parser.add_option("-q", "--quiet", action="store_true", dest="QUIET", help="Avoid all non warning prints")
        parser.add_option("-n", "--nocolor", action="store_false", dest="COLOR", default=True, help="Don't output colored text")
        parser.add_option("-d", "--debug", action="store_true", dest="DEBUG", help="Print debug messages")
        parser.add_option("-f", "--from", dest="FROM", help="from email address")
        parser.add_option("-t", "--to", dest="TO", help="to email address - If specified an email will be sent to this address if the site is down")
        parser.add_option("-c", "--config", dest="CONFIGFILE", default="alive.cfg", help="The configuration file. By default this is alive.cfg in the current directory.")
        parser.add_option("-k", "--test-known", dest="KNOWN", action="store_true", help="Test all existing URLs in the cfg file.")
        parser.add_option("-l", "--list", dest="LIST", action="store_true", help="List known URLs in the config file.")
        parser.add_option("--test", dest="TEST", action="store_true", help="Run unit tests")

        (self.options, args) = parser.parse_args()

        def permission_check(file_name):
            """Check permissions"""

            if not os.path.exists(file_name):
                return

            mod = os.stat(file_name).st_mode
            if mod & stat.S_IRGRP:
                self.write_warn( "%s is group readable\n" % file_name)
            if mod & stat.S_IXGRP:
                self.write_warn( "%s is group executable\n" % file_name)
            if mod & stat.S_IWGRP:
                self.write_warn( "%s is group writable\n" % file_name)
            if mod & stat.S_IROTH:
                self.write_warn( "%s is other readable\n" % file_name)
            if mod & stat.S_IXOTH:
                self.write_warn( "%s is other executable\n" % file_name)
            if mod & stat.S_IWOTH:
                self.write_warn( "%s is other writable\n" % file_name)

        permission_check(sys.argv[0])
        permission_check(self.options.CONFIGFILE)

        if not (self.options.TEST or self.options.URL or self.options.KNOWN or self.options.LIST) or len(args):
            parser.print_help()
            return False

        # Lock such that several instances does not work with the same config file simultaneously
        lockfilename = self.options.CONFIGFILE + "_lock"
        if os.path.exists(lockfilename):
            self.write("Lock file '%s' exists\n" % lockfilename)
            # Read pid from lock file
            lockfile = open(lockfilename)
            pid = lockfile.readline()
            lockfile.close()
            if re.match('\d+', pid):
                if int(pid) == os.getpid():
                    self.write("We have a lockfile for ourself, ignoring\n")
                elif os.path.exists("/proc/" + pid):
                    self.write_warn("Another process (%s) is still alive, aborting.\n" % pid)
                    sys.exit(1)
                else:
                    self.write_warn("we had a lock file but the process is no longer alive. Deleting lock file and will continue...\n")
                    os.remove(lockfilename)
            else:
                self.write_warn("The lockfile did not contain a valid pid. Please check it manually. Aborting.")
                sys.exit(1)

        # We are not locked, then create our lockfile
        lockfile = open(lockfilename,'w')
        lockfile.write("%s" % os.getpid())
        lockfile.close()

        return True

    def write(self, text, color=Color.CYAN):
        """Writes the string only if not in quiet mode"""
        if self.options.COLOR and color:
            sys.stdout.write(color)
        if not self.options.QUIET:
            sys.stdout.write(text)
        if self.options.COLOR and color:
            sys.stdout.write(Color.RESET)
        sys.stdout.flush()

    def write_debug(self, text, color=None):
        """Writes a string prefixed by Debug: only if in debug mode"""
        if not self.options.DEBUG:
            return
        if self.options.COLOR and color:
            sys.stdout.write(color)
        if not self.options.QUIET:
            sys.stdout.write("Debug: " + text)
        if self.options.COLOR and color:
            sys.stdout.write(Color.RESET)
        sys.stdout.flush()

    def write_warn(self, text, color=Color.YELLOW):
        """Writes a string prefixed by Warning: to stderr"""
        if self.options.COLOR and color:
            sys.stderr.write(color)
        sys.stderr.write("Warning: %s" % text)
        if self.options.COLOR and color:
            sys.stderr.write(Color.RESET)
        sys.stderr.flush()

    def check_urls(self, config, urls):
        """Will go through the url list and check if they are up"""

        # Create Site objects
        sites = []
        for url in urls:
            sites += [Site(url, [config], self)]

        state_pos = 30
        for site in sites:
            if len(site.get_url()) > state_pos:
                state_pos = len(site.get_url())

        threads = []
        for site in sites:
            thread = SiteThread(site)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
            site = thread.get_site()
            res = site.get_res()
            self.write( "Result for %s: " % site.get_url() )
            if res and res != 6:
                self.report( site, True, state_pos )
            else:
                self.report( site, False, state_pos )

    def report( self, site, down, state_pos ):
        """Report the state and eventual change"""

        known_earlier = down == site.get_down()

        if down:
            state = "down"
            color = Color.RED
            space = ""
        else:
            state = "up"
            color = Color.GREEN
            space = "  "

        self.write( "%s%s%s" % (space, (state_pos-len(site.get_url()))*" ", state), color)

        if site.get_new():
            self.write( " ( New URL" )
        elif known_earlier:
            self.write( " ( State already known" )
            if site.get_last_change():
                self.write( " since %s" % time.ctime(site.get_last_change()) )
        else:
            self.write( " ( State changed" )
        self.write(")\n")

        if not known_earlier:
            if self.options.TO:
                if( not self.send_mail( "%s %s" % (site.get_url(), state), "Site is %s at %s" % (state, datetime.datetime.now().ctime()) ) ):
                    return
            site.activate_triggers(down)
            site.set_last_change(int(time.time()))

        site.set_down(down)

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

    def write_config(self, config):
        # Write the configuration file
        with open( self.options.CONFIGFILE, 'wb') as configfile:
            config.write(configfile)
            os.chmod(self.options.CONFIGFILE, stat.S_IRUSR | stat.S_IWUSR)

    def setup(self):
        """Read in the config file and URLs"""
        urls = []
        if self.options.URL:
            urls += self.options.URL.split()

        config = ConfigParser.RawConfigParser()
        config.read( self.options.CONFIGFILE )

        if self.options.KNOWN:
            urls += config.sections()

        return (config, urls)

import unittest

class TestAlive(unittest.TestCase):

    def setUp(self):
        """
        This function must be named setUp, it's run
        before each test.
        """
        self.alive = Alive()
        self.configfile = "unittest_test_config"
        try:
            os.remove(self.configfile)
        except:
            pass

    def tearDown(self):
        try:
            os.remove(self.configfile)
        except:
            pass

    def test_empty_config(self):
        sys.argv = [sys.argv[0], "-c", self.configfile, "-l"]
        self.alive.parse_command_line_options()
        (config, urls) = self.alive.setup()
        self.assertEqual(len(config.sections()), 0)

    def url_test(self, url, should_be_up, count=1):
        sys.argv = [sys.argv[0], "-c", self.configfile, "-q", "-u", url]
        self.alive.parse_command_line_options()
        (config, urls) = self.alive.setup()
        self.alive.check_urls(config, urls)
        self.alive.write_config(config)
        (config, urls) = self.alive.setup()
        self.assertEqual(len(config.sections()), count)
        self.assertTrue(config.has_section(url))
        if should_be_up:
            self.assertFalse(config.getboolean(url, "Down"))
        else:
            self.assertTrue(config.getboolean(url, "Down"))

    def test_google(self):
        self.url_test("www.google.no", True)

    def test_down(self):
        self.url_test("www.ifnvernieunviereev.com", False)

    def test_two_sites(self):
        self.url_test("www.ifjirfijfirjfrijfiY.com", False)
        self.url_test("www.ifjirfijfirjfrijfiX.com", False, 2)

    def get_a_site(self, url="www.test.com"):
        sys.argv = [sys.argv[0], "-c", self.configfile, "-q", "-k"]
        self.alive.parse_command_line_options()
        (config, urls) = self.alive.setup()
        return Site(url, [config], self.alive)

    def test_set_get_down_config(self):
        site = self.get_a_site()
        # Sites are assumed to be up by default
        self.assertFalse(site.get_down())
        site.set_down(False)
        self.assertFalse(site.get_down())
        site.set_down(True)
        self.assertTrue(site.get_down())

    def test_set_get_last_change(self):
        site = self.get_a_site()
        # Sites are assumed to have a valid last_change by default
        self.assertTrue(site.get_last_change() > 0)
        # last_change should not be in the future
        self.assertTrue(site.get_last_change() < time.time())
        site.set_last_change(0)
        self.assertTrue(site.get_last_change()==0)
        site.set_last_change(1500)
        self.assertTrue(site.get_last_change()==1500)

    def test_set_get_url(self):
        site = self.get_a_site()
        self.assertTrue(site.get_url() == "www.test.com")

    def test_set_get_new(self):
        site = self.get_a_site()
        self.assertTrue(site.get_new())

    def test_up_trigger(self):
        trigger_file = "up_trigger"
        url = "www.google.no"
        # Remove any eventual old file
        if os.path.exists(trigger_file):
            os.remove(trigger_file)
        # First create a site object for which google is down
        site = self.get_a_site(url)
        site.set_down(True)
        config = site.get_config()
        # Now add a trigger
        config[0].set(url, "up_trigger", "touch %s" % trigger_file)
        self.alive.write_config(config[0])
        self.url_test(url, True)
        # Check if trigger file was created
        self.assertTrue(os.path.exists(trigger_file))
        os.remove(trigger_file)

    def test_down_trigger(self):
        trigger_file = "down_trigger"
        url = "www.afwjkefnwejknfwkejfnwkejnfke.com"
        # Remove any eventual old file
        if os.path.exists(trigger_file):
            os.remove(trigger_file)
        # First create a site object with an invalid url and set it to be up
        site = self.get_a_site(url)
        site.set_down(False)
        config = site.get_config()
        # Now add a trigger
        config[0].set(url, "down_trigger", "touch %s" % trigger_file)
        self.alive.write_config(config[0])
        self.url_test(url, False)
        # Check if trigger file was created
        self.assertTrue(os.path.exists(trigger_file))
        os.remove(trigger_file)

    def test_dual_down_trigger(self):
        trigger_file = "down_trigger"
        trigger_file_2 = "down_trigger_2"
        url = "www.afwjkefnwejknfwkejfnwkejnfke.com"
        # Remove any eventual old file
        if os.path.exists(trigger_file):
            os.remove(trigger_file)
        if os.path.exists(trigger_file_2):
            os.remove(trigger_file_2)
        # First create a site object with an invalid url and set it to be up
        site = self.get_a_site(url)
        site.set_down(False)
        config = site.get_config()
        # Now add a trigger
        config[0].set(url, "down_trigger", "touch %s; touch %s" % (trigger_file, trigger_file_2))
        self.alive.write_config(config[0])
        self.url_test(url, False)
        # Check if trigger file was created
        self.assertTrue(os.path.exists(trigger_file))
        os.remove(trigger_file)
        self.assertTrue(os.path.exists(trigger_file_2))
        os.remove(trigger_file_2)


    def test_known(self):
        # First just add two urls to the config file
        url_up   = "www.google.no"
        url_down = "aefasdfasdfopj"
        self.alive.parse_command_line_options()
        (config, urls) = self.alive.setup()
        config.add_section(url_up)
        config.add_section(url_down)
        self.alive.write_config(config)

        # Then lets test the existing urls from the file
        sys.argv = [sys.argv[0], "-c", self.configfile, "-q", "-k"]
        self.alive.parse_command_line_options()
        (config, urls) = self.alive.setup()
        self.alive.check_urls(config, urls)
        self.alive.write_config(config)
        (config, urls) = self.alive.setup()
        self.assertEqual(len(config.sections()), 2)
        self.assertTrue(config.has_section(url_up))
        self.assertTrue(config.has_section(url_down))
        self.assertFalse(config.getboolean(url_up, "Down"))
        self.assertTrue(config.getboolean(url_down, "Down"))

    # TODO: Should check the Time value, and command line options

def main():
    """main"""

    alive = Alive()

    if not alive.parse_command_line_options():
        sys.exit(1)

    if alive.options.TEST:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAlive)
        unittest.TextTestRunner(verbosity=2).run(suite)
        os.remove("unittest_test_config" + "_lock")
    else:
        (config, urls) = alive.setup()

        if alive.options.LIST:
            if len(config.sections()):
                alive.write("Known URLs in the config file '%s':\n\n" % alive.options.CONFIGFILE)
                for url in config.sections():
                    print url
            else:
                alive.write("No URLs in the config file '%s'\n" % alive.options.CONFIGFILE)
        else:
            alive.check_urls(config, urls)
            alive.write_config(config)

    lockfilename = alive.options.CONFIGFILE + "_lock"
    os.remove(lockfilename)

if __name__ == "__main__":
    main()
