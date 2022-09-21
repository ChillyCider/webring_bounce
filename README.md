webring-jump
============

This [WSGI](https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface) app provides bounce URLs to HTML-driven [webrings](https://en.wikipedia.org/wiki/Webring).

[Click here for a demo.](https://chillycider.github.io/webring/)

Bounce URLs
-----------

* Random site: `/random?ring=...`
* Next site: `/next?ring=...&from=...`
* Previous site: `/prev?ring=...&from=...`

Define webrings directly in HTML
--------------------------------

See the bounce URLs? The `ring` argument should be a URL to a webpage. The app will scan that webpage for `<a>` elements with their `rel` attribute set to `"webring-member"`.  Example:

```html
<p>Welcome to my Grand Canyon webring!!! The members of this ring are:</p>
<ul>
    <li><a rel="webring-member" href="https://example.org/">Best picture spots in the Grand Canyon</a></li>
    <li><a rel="webring-member" href="https://example.net/">History: The Grand Canyon</a></li>
</ul>
```

That's all `/random` needs. The app will then bounce
the user to a randomly chosen link.

`/next` and `/prev` both require a second argument, called `from`.
This specifies the **user's current location** on the ring, so that they
can be shuttled to the next or previous one accordingly.

And that's how it works.

Running for local development
-----------------------------

Invoking `webring_bounce.py` will start Python's built-in WSGI server.

```bash
$ export WEBRING_WHITELIST="https://chillycider.github.io/webring/"
$ export CACHE_SPEC=sqlite://webring_cache.db
$ export HOST=127.0.0.1
$ export PORT=3000
$ python3 webring_bounce.py
webring_bounce v0.1
===================
Listening on 127.0.0.1 port 3000.

*  Note: You are using the built-in Python WSGI server. If this service
*  is intended to be accessible from the public Internet, then please
*  use a more secure server such as gunicorn (Green Unicorn).

```

Deploying for real
------------------

Here's a workable example for [gunicorn](https://gunicorn.org/).

```bash
$ gunicorn -k gevent -b 0.0.0.0:3000 -w 3 \
      -e WEBRING_WHITELIST="https://chillycider.github.io/webring/" \
      -e CACHE_SPEC=sqlite:///tmp/webring_cache.db \
      webring_bounce:app
```

Frequently Asked Questions
--------------------------

### Why do webrings have to be whitelisted?

It's a security measure to stop bots from flooding the SQLite cache
with URLs. It's also a first line of defense against abuse such as
that described in [issue #1](https://github.com/ChillyCider/webring_bounce/issues/1).

Consider also that a strict whitelist makes it tough for instances to get too widely used,
discouraging a [single point of failure](https://en.wikipedia.org/wiki/Single_point_of_failure).

### Why does this app even exist?

To increase the capabilities of HTML-only websites such as those hosted on [Neocities](https://neocities.org/).

License
-------

&copy; 2022 Charlie Murphy. This software is released under the terms of the [Unlicense](LICENSE.txt).

Contributing
------------

This project is open to new ideas and pull requests. Also, if you find a bug, feel free to tell us on [the issue tracker](https://github.com/ChillyCider/webring_bounce/issues).

If you want to submit a PR, I require that you include this disclaimer
with your PR:

> I dedicate any and all copyright interest in this software to the public domain. I make this dedication for the benefit of the public at large and to the detriment of my heirs and successors. I intend this dedication to be an overt act of relinquishment in perpetuity of all present and future rights to this software under copyright law.

Attaching that to your PR will keep the project unquestionably in the public domain.
