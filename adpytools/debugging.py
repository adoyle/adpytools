#! /usr/bin/env python
"""
debugging - inspired by the debugging.h and error_handling.c modules
            of OpenMap's C-based "toollib" that I originally wrote
            in the 90's while at BBN.


Debug([word])

        Looks in the current environment (via getenv) to look for
        an environment variable called 'DEBUG'.

        If there is none, then it returns False
        If there is one, and it was called with an argument, then
        if the DEBUG variable contains that argument, it returns True
        otherwise, it returns false. Note that it does this with
        'word' boundaries.
        
        Examples:

        Assume no DEBUG environment variable is set
                Debug() --> False
                Debug("foo") --> False
                Debug("bar") --> False

        Assume DEBUG is set to "foo foobar"
        
                Debug() --> True
                Debug("foo") --> True
                Debug("bar") --> False

DebugSet([word])

        Allows you to add strings to the set that are in the DEBUG
        environment variable.

        Examples:

        Assume DEBUG is set to "foo foobar"
                DebugSet("bar")
                Debug("bar") now returns True

DebugUnset([word])

        If called with no arguments, it makes all subsequent calls to Debug
        return False

        If called with a word, it makes all subsequent calls to Debug with
        that word return False
        
DebugMessage(message, [level])

        message is a string
        level is one of "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"

        Prints the message to stderr, along with date, time, level, and
        source file name and line number where the call was made.
"""

# ------------------------------------------------------------------------
# 
# Copyright (c) 2006 Allan Doyle
# Copyright (c) 2006 EOGEO
# 
#  Permission is hereby granted, free of charge, to any person
#  obtaining a copy of this software and associated documentation
#  files (the "Software"), to deal in the Software without
#  restriction, including without limitation the rights to use, copy,
#  modify, merge, publish, distribute, sublicense, and/or sell copies
#  of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
# 
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
# 
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
# 
# ------------------------------------------------------------------------

import inspect
import logging
import os
import os.path
import sys

## Set up the Debug part of this code...

__vars = {}
__debug = os.getenv("DEBUG")

if __debug:
    __vars[' '] = ' '  # we use ' ' as a marker for DEBUG
    # being set, even if it has no content

    try:
        # each separate string in DEBUG gets used as a key in a dictionary
        # later on, this makes it easy to tell if that string was set
        for v in os.getenv("DEBUG").split():
            __vars[v] = v

    except AttributeError:
        pass
    except TypeError:
        pass


def Debug(name=" "):
    """
    Checks to see if the "DEBUG" environment variable is set, if
    an optional string is passed in, if that string is set in the
    "DEBUG" environment variable.
    """
    global __vars
    return name in __vars


def DebugSet(name=" "):
    """
    If called with no argument, causes subsequent calls to Debug() to
    return True. If called with an argument, causes subsequent calls
    to Debug() with the same string to return True
    """

    global __vars
    global __debug

    __debug = True
    __vars[name] = name
    return (True)


def DebugUnset(name=" "):
    """
    If called with no argument, causes subsequent calls to Debug() to
    return False. If called with an argument, causes subsequent calls
    to Debug() with the same string to return False.
    """
    global __vars
    global __debug

    if name == " ":
        __debug = False
        __vars = {}
        return

    try:
        del __vars[name]

    except KeyError:
        pass

    return

    ## Set up the DebugMessage part of this. We use the logging module,
    ## but send everything to stderr. Someday, this could get expanded
    ## to also have a logfile, etc.


logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)-8s %(message)s',
                    stream=sys.stderr)

levels = {
    'CRITICAL': logging.critical,
    'ERROR': logging.error,
    'WARNING': logging.warning,
    'INFO': logging.info,
    'DEBUG': logging.debug
}


def DebugMessage(msg, level="DEBUG"):
    """
    Produces nicely formatted output to stderr.
    If called with the wrong level, it complains, and behaves
    as though the level was "ERROR"
    If called with no level, it uses "DEBUG"
    The allowed levels are
      "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"
    """

    current = inspect.currentframe()
    outer = inspect.getouterframes(current)

    try:
        levels[level]('%s - %4d: %s' % (os.path.basename(outer[1][1]),
                                        outer[1][2], msg))

    except KeyError:
        DebugMessage('DebugMessage() called with unknown level: %s' % level)
        logging.error('%s - %4d: %s' % (os.path.basename(outer[1][1]),
                                        outer[1][2], msg))
    del outer
    del current


__version__ = '$Id: debugging.py 4 2007-05-09 13:50:41Z adoyle $'
if Debug('version'): print(__version__)
