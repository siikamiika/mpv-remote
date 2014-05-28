from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qsl, quote
from pathlib import Path
from functools import cmp_to_key
from subprocess import call

base = """<head>
<style>
body {background-color: black; color: white;}
a:link {color: white;}
a:visited {color: #aaaaaa}
.folder {background-color: blue;}
.file {background-color: green;}
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
        else:
            listing = ['<h1>{}</h1><hr><ul>'.format(d)]

            def sort_cmp(a, b):
                if a.is_dir() and b.is_dir():
                    return (a > b)*2 - 1
                elif a.is_dir() and b.is_file():
                    return -1
                elif a.is_file() and b.is_dir():
                    return 1
                elif a.is_file and b.is_file():
                    return (a > b)*2 - 1
                else:
                    return 0
                    
            for x in sorted(d.iterdir(), key=cmp_to_key(lambda x, y: sort_cmp(x,y))):
                link = quote(str(x))
                text = str(x).split('/')[-1]
                if x.is_file():
                    listing.append(
                        '<li><a class="file" href="?play={link}">{text}</a></li>'.format(
                            link=link, text=text))
                elif x.is_dir():
                    listing.append(
                        '<li><a class="folder" href="?dir={link}/">{text}/</a></li>'.format(
                            link=link, text=text))
            listing.append('</ul>')

            self.respond_ok((base + ''.join(listing)).encode())

    def play_file(self, fpath):
        self.respond_ok('file playing...'.encode())
        call(['mpv', fpath])


    def do_GET(self):

        qs_list = dict(parse_qsl(urlparse(self.path).query))
        dir_path = qs_list.get('dir')
        play_path = qs_list.get('play')

        if dir_path:
            self.list_dir(dir_path)
        elif play_path:
            self.play_file(play_path)
        elif self.path == '/':
            self.respond_ok('asdf'.encode())

        else:
            self.respond_notfound()


srv = HTTPServer(('', 9876), MpvRequestHandler)
srv.serve_forever()
