#!/usr/bin/env python3

import os
import json
import time
import random
import hashlib
import sqlite3
import urllib.parse
import urllib.request
import urllib.error
import html
from html.parser import HTMLParser

VERSION = '0.1'

# HTTP responses

class NotFound(object):
    def emit(self, start_response):
        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return [b'<h1>404 Not Found</h1>']

class Unprocessable(object):
    def __init__(self, reason):
        self.reason = reason

    def emit(self, start_response):
        start_response('422 Unprocessable Entity', [('Content-Type', 'text/html')])
        return [b'<h1>422 Unprocessable Entity</h1><p>' + html.escape(self.reason).encode('utf-8') + b'</p>']

class Found(object):
    def __init__(self, location):
        self.location = location
    
    def emit(self, start_response):
        start_response('302 Found', [('Location', self.location)])
        return [
            b'<h1>302 Found</h1>',
            b'<p>If you aren\'t redirected in the next few seconds, <a href="',
            html.escape(self.location, True).encode('utf-8'),
            b'">click here</a>.</p>'
        ]

class WebringSourceParser(HTMLParser):
    """An HTML parser that finds all the <a rel="webring-member"> links
    on a page."""
    def __init__(self):
        super().__init__()
        self.sites = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attr_dict = { k: v for k, v in attrs }

            if 'href' in attr_dict and 'rel' in attr_dict and attr_dict['rel'] == 'webring-member':
                self.sites.append(attr_dict['href'])

class SqliteCache(object):
    def __init__(self, path):
        self.con = None
        self.path = path

    def __enter__(self):
        self.con = sqlite3.connect(self.path)
        self.con.execute(""" CREATE TABLE IF NOT EXISTS cache (
                                 id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                                 key TEXT NOT NULL UNIQUE,
                                 value TEXT NOT NULL
                             ) """)
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.con:
            self.con.close()
    
    def get(self, key):
        cur = self.con.execute(""" SELECT value FROM cache
                                   WHERE key = ?
                                   LIMIT 1 """, (key,))
        result = cur.fetchone()
        if result is not None:
            result = result[0]
        return result

    def set(self, key, value):
        self.con.execute("UPDATE OR IGNORE cache SET value = ? WHERE key = ?", (value, key))
        self.con.execute("INSERT OR IGNORE INTO cache (key, value) VALUES (?, ?)", (key, value))
        self.con.execute("COMMIT")

def cache_factory(spec):
    parts = spec.split('://', 1)
    if parts[0] == 'sqlite':
        if len(parts) == 1:
            raise ValueError('SQLite cache provider requires a path, e.g. sqlite:///tmp/webring_cache.db')
        
        return SqliteCache(parts[1])
    else:
        raise ValueError('Could not understand cache provider spec %r' % (spec,))

def get_sites(cache_opener, ring):
    """Get a webring's member sites, checking the cache first."""

    key = hashlib.sha256(ring.encode('utf-8')).hexdigest()[0:12]

    with cache_opener as cache:
        etag = None

        cached_raw = cache.get(key)
        if cached_raw:
            cached_dict = json.loads(cached_raw)
            if time.time() < cached_dict['retrieved_at'] + 60:
                return cached_dict['sites']
            
            etag = cached_dict.get('etag', None)

        headers = {}
        if etag:
            headers['If-None-Match'] = etag 
        
        req = urllib.request.Request(ring, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                new_etag = response.headers.get('ETag', None)
                html = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return cached_dict['sites']
            else:
                raise e

        parser = WebringSourceParser()
        parser.feed(html)
        parser.close()

        sites = parser.sites

        entry = { 'retrieved_at': time.time(), 'sites': sites }

        if new_etag:
            entry['etag'] = new_etag

        cache.set(key, json.dumps(entry))

    return sites

def v_next(cache_opener, whitelist, args):
    """The bounce URL to go forward in the webring."""

    ring = args.get('ring', [None])[0]
    if ring in whitelist:
        from_url = args.get('from', [None])[0]
        if from_url is not None:
            sites = get_sites(cache_opener, ring)

            try:
                i = sites.index(from_url)
            except ValueError:
                return Unprocessable("The site you came from is not in the webring.")
            
            return Found(sites[(i + 1) % len(sites)])
        return Unprocessable("No \"from\" parameter was given.")
    return Unprocessable("That webring is not whitelisted.")

def v_prev(cache_opener, whitelist, args):
    """The bounce URL to go to back in the webring."""

    ring = args.get('ring', [None])[0]
    if ring in whitelist:
        from_url = args.get('from', [None])[0]
        if from_url is not None:
            sites = get_sites(cache_opener, ring)

            try:
                i = sites.index(from_url)
            except ValueError:
                return Unprocessable("The site you came from is not in the webring.")
            
            return Found(sites[(i - 1) % len(sites)])
        return Unprocessable("No \"from\" parameter was given.")
    return Unprocessable("That webring is not whitelisted.")
    

def v_random(cache_opener, whitelist, args):
    """The bounce URL to go to a random site in the webring."""

    ring = args.get('ring', [None])[0]
    if ring in whitelist:
        sites = get_sites(cache_opener, ring)

        from_url = args.get('from', [None])[0]
        if from_url is not None:
            sites.remove(from_url)
        
        new_site = random.choice(sites)
        return Found(new_site)
    return Unprocessable("That webring is not whitelisted.")

ROUTES = { '/next': v_next, '/prev': v_prev, '/random': v_random }

def handle_request(cache_opener, whitelist, environ):
    path = environ['PATH_INFO']
    if path in ROUTES:
        args = urllib.parse.parse_qs(environ['QUERY_STRING'])
        route = ROUTES[path]
        return route(cache_opener, whitelist, args)
    
    return NotFound()

def create_app(cache_opener, whitelist):
    def app(environ, start_response):
        return handle_request(cache_opener, whitelist, environ).emit(start_response)
    
    return app

app = create_app(
    cache_factory(os.environ.get('CACHE_SPEC', 'sqlite://webring_cache.db')),
    os.environ.get('WEBRING_WHITELIST', '').split()
)

if __name__ == '__main__':
    import sys
    import wsgiref.simple_server

    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 3000))

    print("webring_bounce " + VERSION, file=sys.stderr)
    print("=" * len("webring_bounce " + VERSION), file=sys.stderr)

    with wsgiref.simple_server.make_server(host, port, app) as httpd:
        print('Listening on %s port %d.' % (host, port), file=sys.stderr)
        print("""
*  Note: You are using the built-in Python WSGI server. If this service
*  is intended to be accessible on the public Internet, then we
*  recommend using a more secure server such as gunicorn (Green Unicorn).
""", file=sys.stderr)
        httpd.serve_forever()
