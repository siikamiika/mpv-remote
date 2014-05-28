from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qsl, quote
from pathlib import Path
from functools import cmp_to_key
from subprocess import Popen
from os import sep
from os.path import expanduser

base = """<head>
<meta name="viewport" content="width=device-width, user-scalable=no" />
<style>
body {background-color: black; color: white;}
a:link {color: white;}
a:visited {color: #aaaaaa}
.folder {background-color: blue;}
.video {background-color: green;}
li {margin-bottom: 1em;}
</style>
</head>
"""

class MpvRequestHandler(BaseHTTPRequestHandler):

    def respond_ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(data)

    def respond_notfound(self, data=None):
        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(data or '404'.encode())

    def list_dir(self, path):
        d = Path(path)
        if not d.is_dir():
            self.respond_notfound()
            return
        parts = str(d).split(sep)
        links = '<a href="/?dir=/">(root)</a>' + sep.join(
            '<a href="/?dir={0}/">{1}</a>'.format(
                sep.join(parts[:parts.index(d_)+1]), d_)
                for d_ in parts
            )
        listing = ['<h1>{}</h1><hr><ul>'.format(links)]

        def sort_cmp(a, b):
            if a.is_dir() == b.is_dir():
                return (a > b)*2 - 1
            elif a.is_dir():
                return -1
            elif a.is_file():
                return 1

        for x in sorted(d.iterdir(), key=cmp_to_key(lambda x, y: sort_cmp(x,y))):
            link = quote(str(x))
            text = str(x).split('/')[-1]
            if x.is_file():
                vid = False
                vid_ext = ['avi', 'mp4', 'mkv', 'ogg', 'flv', 'm4v', 'mov', 'mpg', 'mpeg', 'wmv']
                if text.split('.')[-1] in vid_ext:
                    vid = True
                listing.append(
                    '<li><a class="{cls}" href="/?play={link}">{text}</a></li>'.format(
                        cls=('video' if vid else 'file'), link=link, text=text))
            elif x.is_dir():
                listing.append(
                    '<li><a class="folder" href="/?dir={link}/">{text}/</a></li>'.format(
                        link=link, text=text))
        listing.append('</ul>')

        self.respond_ok((base + ''.join(listing)).encode())

    def play_file(self, fpath):
        self.respond_ok('file playing...'.encode())
        Popen(['mpv', '--lua=commandbridge.lua', '--fs', '--force-window', fpath])


    def do_GET(self):

        qs_list = dict(parse_qsl(urlparse(self.path).query))
        dir_path = qs_list.get('dir')
        play_path = qs_list.get('play')

        if dir_path:
            self.list_dir(dir_path)
        elif play_path:
            self.play_file(play_path)
        elif self.path == '/':
            homedir = expanduser('~')
            self.send_response(302)
            self.send_header('Location', '/?dir='+quote(homedir))
            self.end_headers()
        else:
            self.respond_notfound()


srv = HTTPServer(('', 9876), MpvRequestHandler)
srv.serve_forever()
