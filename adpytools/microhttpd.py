#!/usr/bin/env python

# ------------------------------------------------------------------------
# 
# Copyright (c) 2007 Allan Doyle
# Copyright (c) 2007 MIT Museum - derived from mwowserver.py,
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
"""httpserver.py

micro http request dispatcher

Lets you bind arbitrary functions or class methods to URLs.

Given an entire URL, this searches through the bindings to figure out
a match.  Only whole "words" match. I.e. something bound to /foo/bar
will match URLS like
        
        /foo/bar/baz
        /foo/bar/
        /foo/bar?baz=2

but will not match

        /foo/bartsimpson
        /foo/ba

Also, if you bind

        /foo            to one function and
        /foo/bar        to another

Then anything beginning with /foo/bar will match the latter and
anything beginning with /foo but not /foo/bar will match the
former. Basically, the match works backwards, one URL segment at a
time to look for a match.

Matches work if extensions are present as well. An emerging trend in
REST is to use things like /foo.json or /foo.html to ask for specific
representations. This is in addition to, or even instead of, the
Accept header in HTTP.

Thus /foo and /foo.something will both match /foo

Also /foo?stuff and /foo.something?stuff will also match /foo

In any case, the extension consists of a '.' followed by whatever came
after, up to an eventual '?' character.

The root URL is handled a bit differently, only '/' and '/' followed
by arguments will work. E.g. these work:

        /
        /?message=hello

These do not:

        /test
        /test?foo
        
However, if you set a "default", that will catch all urls not caught
as described above.

If you do not set a "default", then the microserver will let you do
GETs on files and subdirectories. Be careful to make sure this is what
you want! (Maybe there should be a way to set/clear this behavior with
a method in dispatch...)

There's a URL munging function that lets you correct for the use of
Apache (or other) rewriting schemes.

Each function or method is called with these arguments -

  type  GET, PUT, POST, DELETE, etc.
  match The part of the incoming URL that matched
  ext   The part of the incoming URL behind the last '.' character
        e.g. '.ext' from 'match.ext'
  rest  The rest of the incoming URL after the match and any ext
  note  An optional string that was passed in at bind time (or None)

  GET on /foo/bar.baz?stuff matched to /foo/bar would yield:

          type:  GET
          match: /foo/bar
          ext:   .baz
          rest:  ?stuff
  
Each function must return a dictionary with the following information:
{
  'c': <http result code>       OPTIONAL - if you leave this off,
                                it defaults to httplib.OK, if you use
                                it, then 1xx, 2xx, and 3xx return
                                normally
                                4xx and 5xx use BaseHTTPServer.send_error

  'r': response body            OPTIONAL - if you leave this off,
                                it defaults to nothing being returned.
                                If you use it, then it's a string of all
                                the data to be returned.

  'h': list of headers          OPTIONAL - if you leave this off, then
                                the 'standard' headers for your response
                                are returned, If you use it, then it should
                                be a list of two-item tuples, the first
                                item is the header name, the second 
                                is the content.
}

Example:

import microhttpd
microhttpd.server.dispatch.bind('/version', microhttpd.echo, microhttpd.__version__)
microhttpd.server.dispatch.bind('/exit', microhttpd.exit)
microhttpd.server.dispatch.bind('/', microhttpd.echo, "Hello World\n")
microhttpd.server.serve_forever()

"""

# Python imports
import sys
import os
import SocketServer
import httplib
import time
import BaseHTTPServer
import SimpleHTTPServer

# adpytools imports
from debugging import Debug
__version__ = '$Id: microhttpd.py 11 2007-05-23 18:31:48Z adoyle $'
if Debug("version"): print __version__

# used to track requests in multi-threaded mode
serial = 0


# Some sample functions. Should probably be contingent on __main__
def exit(type, match, ext, rest, note):
    """Makes the server exit."""
    os._exit(0)


def echo(type, match, ext, rest, note):
    """Returns a string with its arguments encoded into the string"""
    return ({
        'h': [('Content-type', "text/plain")],
        'r': "echo type:" + type + " match:" + match + " ext:" + ext + " rest:"
        + rest + " note:" + repr(note)
    })


def urltest(type, match, ext, rest, note):
    """Returns some HTML that should contain a link back to itself"""
    return ({
        'h': [('Content-type', "text/html;charset=utf-8")],
        'r': '<html><body>urltest: ' + '/urltest -> <a href="' +
        server.dispatch.munge_url('/urltest') + '>' +
        server.dispatch.munge_url('/urltest') + '</a></body></html>'
    })


class Dispatch:
    def __init__(self):
        self.bindings = {}
        self.default = None
        self.baseurl = ""
        pass

    def set_baseurl(self, baseurl):
        """
        This lets you do things like rewrite the URLs.
        E.g. this call:
        
         server.dispatch.set_baseurl("http://localhost/tester")
        
        would handle using Apache to rewrite with these rules:
        
          RewriteCond %{REQUEST_URI} ^/tester/
          RewriteRule ^/tester(.*) http://localhost:8080$1 [L,P]
        
        The urltest function uses dispatch.munge_url() to fix up
        the url being returned in the web page.
        
        """
        self.baseurl = baseurl

    def get_baseurl(self):
        return self.baseurl

    def munge_url(self, url):
        return self.baseurl + url

    def bind(self, url, method, note=None):
        self.bindings[url] = {"method": method, "note": note}

    def unbind(self, url):
        try:
            del self.bindings[url]
        except:
            pass

    def call(self, url, type, data):
        match = url.rsplit('?', 1)[0]  # Strip off ?baz=bop... stuff

        while len(match) > 0:
            if (match.split('/')[-1:][0].rpartition('.')[2] ==
                match.split('/')[-1:][0]):
                # no trailing .ext
                match = match
                ext = ''
            else:
                # trailing .ext
                # Note: since the match = line changes match, it has to be
                # the 2nd one below...
                ext = '.' + match.rpartition('.')[2]
                match = match.rpartition('.')[0]

            if self.bindings.has_key(match):
                if type != 'PUT':
                    data = url[len(match + ext):]
                return self.bindings[match]["method"](
                    type=type,
                    match=match,
                    ext=ext,
                    rest=data,
                    note=self.bindings[match]["note"])
            else:
                match = match.rsplit('/', 1)[0]

        if self.bindings.has_key("default"):
            if type != 'PUT':
                data = url
            return self.bindings["default"]["method"](
                type=type,
                match='',
                ext='',
                rest=data,
                note=self.bindings["default"]["note"])

        return {'r': None, 'c': httplib.NOT_FOUND, 'h': None}

        return {'r': None, 'c': httplib.NOT_FOUND, 'h': None}


class MyHTTPRequestHandler(SocketServer.ThreadingMixIn,
                           SimpleHTTPServer.SimpleHTTPRequestHandler):
    """
    Doc me.
    """

    def do_all(self, type):
        global serial
        serial += 1
        r = {'r': None, 'c': httplib.OK, 'h': None}

        if Debug("httptime"):
            start = time.time()
            print "TIME:%d %s" % (serial, self.path[:25])

        if Debug("http"):
            print self.headers
            print '   size', self.headers.get('Content-Length', '')

        # Dispatch to the right function
        data = ''
        if type == 'PUT':
            self.send_response(httplib.CONTINUE,
                               httplib.responses[httplib.CONTINUE])
            try:
                size = int(self.headers.get('Content-Length', ''))
                data = self.rfile.read(size)
            except:
                data = ''

        result = self.dispatch.call(self.path, type, data)

        r.update(result)
        if Debug("http"): print "do_all:  %s, %s" % (result, self.path[:25])
        if Debug("httptime"):
            print "TIME:%d %.3f" % (serial, time.time() - start)

        # Maybe we should put this behavior on a switch. Right now, if the
        # dispatcher was not able to handle the request, then we return None
        # and let the default SimpleHTTPServer try to handle it.

        if r['c'] is httplib.NOT_FOUND:
            return None  # Hand off to the "regular" SimpleHTTPServer

        # Note that send_error is purely a convenience and may get in the way at some
        # point. It sends back an HTML respose with the error info in it.
        if r['c'] >= httplib.BAD_REQUEST:
            self.send_error(r['c'], httplib.responses[r['c']])
        else:
            self.send_response(r['c'], httplib.responses[r['c']])

        # HTTP 1.1 requires a Content-Length header, compute it and add to the headers
        # This means that thekre will be at least one header
        if r['r'] is not None:
            cl = len(r['r'])
        else:
            cl = 0

        if r['h'] is None:
            r['h'] = [('Content-Length', cl)]
        else:
            r['h'].append(('Content-Length', cl))

        # send the headers
        for header in r['h']:
            if Debug("http"): print "%s: %s" % header
            self.send_header(header[0], header[1])

        self.end_headers()

        if r['r'] is not None:
            self.wfile.write(r['r'])
            if Debug("http"):
                print ''
                if len(r['r']) < 512:
                    print r['r']
                else:
                    print r['r'][:256]
                    print '  ...'
                    print r['r'][-256:]
        print '-=-=-=\n\n'

        self.connection.close()
        return True

    def do_POST(self):
        self.do_all("POST")

    def do_PUT(self):
        self.do_all("PUT")

    def do_DELETE(self):
        self.do_all("DELETE")

    def do_GET(self):
        if self.do_all("GET") is None:
            SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)


class Server:
    def __init__(self):
        self.dispatch = Dispatch()
        MyHTTPRequestHandler.dispatch = self.dispatch

        # 1.1 requires sending 'Content-Length'
        # 1.0 does not, but it doesn't hurt
        MyHTTPRequestHandler.protocol_version = "HTTP/1.1"
        self.ip_and_port()

    def ip_and_port(self, ip='127.0.0.1', port=8000):
        self.server_address = (ip, port)

    def serve_forever(self):
        self.httpd = BaseHTTPServer.HTTPServer(self.server_address,
                                               MyHTTPRequestHandler)
        sa = self.httpd.socket.getsockname()
        print "Serving HTTP on", sa[0], "port", sa[1], "..."
        self.httpd.serve_forever()


if __name__ == '__main__':
    import os
    import sys

    # Use  this as an example, or modify the code in-place to suit your needs
    #

    from optparse import OptionParser, OptionError
    usage = "usage: %prog [-p httpport] [-i ipaddress]"
    parser = OptionParser(usage, version="%prog $Revision: 11 $")

    class Usage(Exception):
        """Exception class for main() - raised if the usage is incorrect"""

        def __init__(self, msg):
            self.msg = msg

    parser.add_option("-p", "--port",
                      action="store",
                      type="int",
                      dest="port",
                      default=8000,
                      help="HTTP port to listen to. Default is 8000")
    parser.add_option("-i", "--ip",
                      action="store",
                      type="string",
                      dest="ip",
                      default="127.0.0.1",
                      help="IP address to listen on. Default is 127.0.0.1")
    parser.add_option(
        "-n", "--nohttp",
        action="store_true",
        dest="nohttp",
        default=False,
        help=
        "Stop printing HTTP traffic to stderr - DANGER, this just kills stderr...")
    server = Server()

    argv = sys.argv
    try:
        try:
            (opts, args) = parser.parse_args(argv)
        except OptionError, msg:
            raise Usage(msg)

    except Usage, err:
        print >> sys.stderr, err.msg
        print >> sys.stderr, "for help use --help"
        os._exit(2)

    if opts.nohttp:
        try:
            fsock = open('/dev/null', 'w')
            sys.stderr = fsock
        except:
            print "Error redirecting stderr"
            os._exit(0)

    print 'port:', opts.port, 'ip:', opts.ip

    server.ip_and_port(opts.ip, opts.port)

    server.dispatch.set_baseurl("http://localhost/tester")

    server.dispatch.bind('/version', echo, __version__)
    server.dispatch.bind('/urltest', urltest)
    server.dispatch.bind('/exit', exit)
    server.dispatch.bind('/', echo, "index")
    server.dispatch.bind('/foo', echo, "index")
    server.dispatch.bind('/foo/bar', echo, "index")
    #    server.dispatch.bind('default', echo, "default")
    server.serve_forever()
