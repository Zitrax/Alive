#!/usr/bin/python
"""
Unit tests for alive.py
"""

import unittest
import sys
import os

from alive import *


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
        self.assertEqual([], urls)

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
        (config, _) = self.alive.setup()
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
        self.assertTrue(site.get_last_change() == 0)
        site.set_last_change(1500)
        self.assertTrue(site.get_last_change() == 1500)

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

    def test_up_trigger_pipe(self):
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
        config[0].set(url, "up_trigger", "ls|wc > %s" % trigger_file)
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
        url_up = "www.google.no"
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

    suite = unittest.TestLoader().loadTestsFromTestCase(TestAlive)
    unittest.TextTestRunner(verbosity=2).run(suite)
    os.remove("unittest_test_config" + "_lock")

if __name__ == "__main__":
    main()
