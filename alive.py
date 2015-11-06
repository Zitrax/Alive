#!/usr/bin/python
"""
This script takes as input a URL and checks with wget if it can be accessed,
with mail notifications when the site goes up or down.
"""

from optparse import OptionParser
import datetime
import os
import re
import stat
import subprocess
import sys
import threading
import time

# Python 2 and 3 support
try:
    import queue
except ImportError:
    import Queue as queue

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


import smtplib
from email.mime.text import MIMEText


class SiteThread(threading.Thread):
    """Manages one site in a thread"""

    results_queue = queue.PriorityQueue()

    def __init__(self, site):
        threading.Thread.__init__(self)
        self.__site = site

    def run(self):
        self.__site.get_res()
        SiteThread.results_queue.put(self.__site)

    def get_site(self):
        return self.__site


class Site(object):
    """Class that handles one site to check"""

    def __init__(self, url, config, alive):
        """We need to pass by reference so pass the config as an array wrapper"""
        self.__url = url
        self.__config = config
        self.__alive = alive
        self.__res = None
        self.__time = None
        self.__start = None
        if not config[0].has_section(url):
            config[0].add_section(url)
            self.__new = True
        else:
            self.__new = False
        try:
            self.__down = config[0].getboolean(url, "down")
        except ValueError:
            self.__down = False
        except configparser.NoOptionError:
            self.__down = False
        try:
            self.__last_change = config[0].getint(url, "time")
        except (ValueError, configparser.NoOptionError):
            self.__last_change = int(time.time())
            self.set_config(url, "time", self.__last_change)

    def __cmp__(self, other):
        return cmp(self.__time, other.__time)

    def set_config(self, section, key, val):
        if sys.hexversion < 0x03000000:
            self.__config[0].set(section, key, val)
        else:
            self.__config[0][section][key] = str(val)

    def get_last_change(self):
        return self.__last_change

    def set_last_change(self, new_time):
        self.set_config(self.__url, "time", new_time)
        self.__last_change = new_time

    def get_down(self):
        return self.__down

    def set_down(self, down):
        self.set_config(self.__url, "down", "yes" if down else "no")
        self.__down = down

    def get_url(self):
        return self.__url

    def get_time_spent(self):
        return self.__time

    def get_time_since_start(self):
        return (time.time() - self.__start)

    def get_new(self):
        return self.__new

    def get_config(self):
        return self.__config

    def get_res(self):
        if self.__res is None:
            self.check_alive()
        return self.__res

    def has_started(self):
        return self.__start is not None

    def check_alive(self):
        self.__start = time.time()
        wget_args = ["wget", "--no-check-certificate", "--quiet", "--timeout=40", "--tries=3", "--spider",
                     self.get_url()]
        self.__alive.write_debug("Checking using cmd: '" + ' '.join(wget_args) + "'\n")
        wget = subprocess.Popen(args=wget_args)
        self.__res = wget.wait()
        self.__time = self.get_time_since_start()

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
                ret = subprocess.call(command, shell=True)
            except OSError:
                pass
            if ret:
                self.__alive.write_warn("could not run '%s'\n" % command, Color.YELLOW)


class Color(object):
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    RESET = '\033[39m'


class Alive(object):
    """
    This class takes as input a URL and checks with wget if it can be accessed,
    with mail notifications when the site goes up or down.
    """

    def __init__(self):
        self.options = None

    def permission_check(self, file_name):
        """Check permissions"""

        if not os.path.exists(file_name):
            return

        mod = os.stat(file_name).st_mode
        if mod & stat.S_IRGRP:
            self.write_warn("%s is group readable\n" % file_name)
        if mod & stat.S_IXGRP:
            self.write_warn("%s is group executable\n" % file_name)
        if mod & stat.S_IWGRP:
            self.write_warn("%s is group writable\n" % file_name)
        if mod & stat.S_IROTH:
            self.write_warn("%s is other readable\n" % file_name)
        if mod & stat.S_IXOTH:
            self.write_warn("%s is other executable\n" % file_name)
        if mod & stat.S_IWOTH:
            self.write_warn("%s is other writable\n" % file_name)

    def parse_command_line_options(self):
        """Will parse all self.options given on the command line and exit if required arguments are not given"""

        parser = OptionParser(usage="%prog [options]",
                              description=("This script takes as input one or several URLs "
                                           "and checks with wget if they can be accessed."))
        (self.options, args) = self.add_options(parser).parse_args()

        if self.options.DEBUG:
            self.permission_check(sys.argv[0])
            self.permission_check(self.options.CONFIGFILE)

        if not (self.options.URL or self.options.KNOWN or self.options.LIST) or len(args):
            parser.print_help()
            return False

        # Lock such that several instances does not work with the same config file simultaneously
        lockfilename = self.options.CONFIGFILE + "_lock"
        if os.path.exists(lockfilename):
            self.write("Lock file '%s' exists\n" % lockfilename)
            # Read pid from lock file
            with open(lockfilename) as lockfile:
                pid = lockfile.readline()
            if re.match('\d+', pid):
                if int(pid) == os.getpid():
                    self.write("We have a lockfile for ourself, ignoring\n")
                elif os.path.exists("/proc/" + pid):
                    self.write_warn("Another process (%s) is still alive, aborting.\n" % pid)
                    sys.exit(1)
                else:
                    self.write_warn(("we had a lock file but the process is no longer alive. "
                                     "Deleting lock file and will continue...\n"))
                    os.remove(lockfilename)
            else:
                self.write_warn("The lockfile did not contain a valid pid. Please check it manually. Aborting.")
                sys.exit(1)

        # We are not locked, then create our lockfile
        with open(lockfilename, 'w') as lockfile:
            lockfile.write("%s" % os.getpid())

        return True

    def add_options(self, parser):
        parser.add_option("-u", "--url", dest="URL",
                          help=("URL(s) to try to retrieve. You can write several URLs separated "
                                "by space, but remember to quote the string."))
        parser.add_option("-q", "--quiet", action="store_true", dest="QUIET", help="Avoid all non warning prints")
        parser.add_option("-n", "--nocolor", action="store_false", dest="COLOR", default=False,
                          help="Don't output colored text")
        parser.add_option("-d", "--debug", action="store_true", dest="DEBUG", help="Print debug messages")
        parser.add_option("-f", "--from", dest="FROM", help="from email address")
        parser.add_option("-t", "--to", dest="TO",
                          help=("to email address - If specified an email will "
                                "be sent to this address if the site is down"))
        parser.add_option("-c", "--config", dest="CONFIGFILE", default="alive.cfg",
                          help="The configuration file. By default this is alive.cfg in the current directory.")
        parser.add_option("-k", "--test-known", dest="KNOWN", action="store_true",
                          help="Test all existing URLs in the cfg file.")
        parser.add_option("-l", "--list", dest="LIST", action="store_true", help="List known URLs in the config file.")
        parser.add_option("-s", "--strict", dest="STRICT", action="store_true",
                          help="Strict ordering. Output can be slightly slower but guarantees that the site with shortest response time is printed first.")
        return parser

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
        if self.options and self.options.COLOR and color:
            sys.stderr.write(color)
        sys.stderr.write("Warning: %s" % text)
        if self.options and self.options.COLOR and color:
            sys.stderr.write(Color.RESET)
        sys.stderr.flush()

    def wait_for_all_to_start(self, sites):
        """Wait for all checks to start (for strict ordering)"""
        while True:
            if not all([s.has_started() for s in sites]):
                time.sleep(0.1)
            else:
                break

    def wait_for_later_sites(self, site, sites):
        """Makes sure we allow time for the last started to check
        to get a chance to finish before the currently fastest check
        to ensure strict ordering"""
        tsp = site.get_time_spent()
        last = min(sites, key=lambda s: s.get_time_since_start())
        to_wait = tsp - last.get_time_since_start()
        if to_wait > 0:
            time.sleep(to_wait)
            SiteThread.results_queue.put(site)
            return SiteThread.results_queue.get()
        return site

    def check_urls(self, config, urls):
        """Will go through the url list and check if they are up"""

        # Create Site objects
        sites = []
        for url in urls:
            sites += [Site(url, [config], self)]

        state_pos = 20
        for site in sites:
            if len(site.get_url()) > state_pos:
                state_pos = len(site.get_url())

        threads = []
        for site in sites:
            thread = SiteThread(site)
            threads.append(thread)
            thread.start()

        if self.options.STRICT:
            self.wait_for_all_to_start(sites)

        tlen = len(threads)
        for i in range(tlen):
            site = SiteThread.results_queue.get()
            if self.options.STRICT:
                site = self.wait_for_later_sites(site, sites)
            res = site.get_res()
            self.write(("[{0:0%dd}/{1}] {2}: " % len(str(tlen))).format(i + 1, tlen, site.get_url()))
            if res and res != 6:
                self.report(site, True, state_pos)
            else:
                self.report(site, False, state_pos)

        # Just to be sure
        for thread in threads:
            thread.join()

    def report(self, site, down, state_pos):
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

        self.write("%s%s%s" % (space, (state_pos - len(site.get_url())) * " ", state), color)

        if site.get_new():
            self.write(" ( New URL")
        elif known_earlier:
            self.write(" ( Known")
            if site.get_last_change():
                self.write(" since %s" % time.ctime(site.get_last_change()))
        else:
            self.write(" ( State changed")
        self.write(") Check took %.2f s\n" % site.get_time_spent())

        if not known_earlier:
            if self.options.TO:
                if not self.send_mail("%s %s" % (site.get_url(), state),
                                      "Site is %s at %s" % (state, datetime.datetime.now().ctime())):
                    return
            site.activate_triggers(down)
            site.set_last_change(int(time.time()))

        site.set_down(down)

    def send_mail(self, subject, body):
        """Send a mail using smtp server on localhost"""
        self.write("Mailing...")
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
        except IOError:
            print("Could not send email, do you have an SMTP server running on localhost?")
            return False
        smtp.sendmail(self.options.FROM, [self.options.TO], msg.as_string())
        smtp.quit()
        return True

    def write_config(self, config):
        # Write the configuration file
        with open(self.options.CONFIGFILE, 'w') as configfile:
            config.write(configfile)
            os.chmod(self.options.CONFIGFILE, stat.S_IRUSR | stat.S_IWUSR)

    def setup(self):
        """Read in the config file and URLs"""
        urls = []
        if self.options.URL:
            urls += self.options.URL.split()

        config = configparser.ConfigParser()
        config.read(self.options.CONFIGFILE)

        if self.options.KNOWN:
            urls += config.sections()

        return config, urls


def main():
    """main"""

    alive = Alive()

    if not alive.parse_command_line_options():
        sys.exit(1)

    (config, urls) = alive.setup()

    if alive.options.LIST:
        if len(config.sections()):
            alive.write("Known URLs in the config file '%s':\n\n" % alive.options.CONFIGFILE)
            for url in config.sections():
                print(url)
        else:
            alive.write("No URLs in the config file '%s'\n" % alive.options.CONFIGFILE)
    else:
        alive.check_urls(config, urls)
        alive.write_config(config)

    lockfilename = alive.options.CONFIGFILE + "_lock"
    os.remove(lockfilename)


if __name__ == "__main__":
    main()
