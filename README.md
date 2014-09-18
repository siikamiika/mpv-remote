mpv-remote
==========

Deployment
----------
Should work by running `python3 server.py` if you have mpv installed. On
Windows this means having `mpv.com` in your PATH or mpv-remote files all over
the mpv directory.


To set a password against unauthorized LAN access or CSRF, create a file
called `login` containing `username:password` in your mpv-remote folder.


If you're having problems with it, try deleting/renaming mpv config files or
building the latest git version.

Usage
-----
Open http://example:9876 on your smartphone and you will be redirected to your
home directory. Navigate to media files and click to play them on your HTPC.
