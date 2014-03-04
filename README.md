```
Usage: alive.py [options]

This script takes as input one or several URLs and checks with wget if they
can be accessed.

Options:
  -h, --help            show this help message and exit
  -u URL, --url=URL     URL(s) to try to retrieve. You can write several URLs
                        separated by space, but remember to quote the string.
  -q, --quiet           Avoid all non warning prints
  -n, --nocolor         Don't output colored text
  -d, --debug           Print debug messages
  -f FROM, --from=FROM  from email address
  -t TO, --to=TO        to email address - If specified an email will be sent
                        to this address if the site is down
  -c CONFIGFILE, --config=CONFIGFILE
                        The configuration file. By default this is alive.cfg
                        in the current directory.
  -k, --test-known      Test all existing URLs in the cfg file.
  -l, --list            List known URLs in the config file.
```

## Info

* Static code analysis: [landscape.io](https://landscape.io/github/Zitrax/Alive/master)
* Continuous integration: [![Build Status](https://travis-ci.org/Zitrax/Alive.png?branch=master)](https://travis-ci.org/Zitrax/Alive)