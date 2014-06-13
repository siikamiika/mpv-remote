from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qsl, quote
from pathlib import Path
from functools import cmp_to_key
from subprocess import call
import os
from os.path import expanduser
from threading import Thread
import socket
if os.name == 'nt': from ctypes import windll

class MpvRequestHandler(BaseHTTPRequestHandler):

    base = \
"""<head>
<meta name="viewport" content="width=device-width, user-scalable=no" />
<style>
body {background-color: black; color: white;}
a:link {color: white;}
a:visited {color: #aaaaaa}
.folder {background-color: blue;}
.video {background-color: green;}
li {margin-bottom: 1em;}
.b {text-decoration: none; background-color: blue; padding: 10px 10px 10px 10px;}
</style>
</head>
"""

    commands = dict(
        playpause=b'mp.command("cycle pause")',
        chapter_next=b'mp.command("add chapter 1")',
        chapter_previous=b'mp.command("add chapter -1")',
        vol_up=b'mp.command("add volume 1")',
        vol_down=b'mp.command("add volume -1")',
        mute=b'mp.command("cycle mute")',
        forward_small=b'mp.command("seek 10")',
        back_small=b'mp.command("seek -10")',
        forward_big=b'mp.command("seek 300")',
        back_big=b'mp.command("seek -300")',
        fullscreen=b'mp.command("cycle fullscreen")',
        stop=b'mp.command("stop")',
        sub=b'mp.command("cycle sub")',
        audio=b'mp.command("cycle audio")',
    )

    controls = (base + \
            '<div style="text-align: center; font-size: 200%; padding-top: 2em;">'
            '<a class="b" href="/?control=vol_down">vol -</a>'
            '<a class="b" href="/?control=mute">mute</a>'
            '<a class="b" href="/?control=vol_up">vol +</a><br><br>'
            '<a class="b" href="/?control=chapter_previous">ch -</a>'
            '<a class="b" href="/?control=chapter_next">ch +</a><br><br>'
            '<a class="b" href="/?control=back_big">&lt;&lt;</a>'
            '<a class="b" href="/?control=back_small">&lt;</a>'
            '&nbsp;<a class="b" href="/?control=playpause">&#9658;</a>&nbsp;'
            '<a class="b" href="/?control=forward_small">&gt;</a>'
            '<a class="b" href="/?control=forward_big">&gt;&gt;</a><br><br>'
            '<a class="b" href="/?control=sub">sub</a>'
            '<a class="b" href="/?control=audio">audio</a><br><br>'
            '<a class="b" href="/?control=stop">exit</a>'
            '<a class="b" href="/?control=fullscreen">full</a>'
            '</div>'
            )

    def redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

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
        parts = str(d).split(os.sep)
        links = '<a href="/?dir={root}">(root)</a>|'.format(
            root='WINROOT' if os.name == 'nt' else '/')
        links += os.sep.join(
            '<a href="/?dir={0}/">{1}</a>'.format(
                quote(os.sep.join(parts[:i+1])), d_)
                for i, d_ in enumerate(parts)
            )
        listing = ['<h1>{}</h1><hr><ul>'.format(links)]

        def sort(a, b):
            try:
                sametype = a.is_dir() == b.is_dir()
            except Exception as e:
                print(e)
                sametype = True
            if sametype:
                return (str(a).lower() > str(b).lower())*2 - 1
            elif a.is_dir():
                return -1
            else:
                return 1

        for x in sorted(d.iterdir(), key=cmp_to_key(lambda x, y: sort(x,y))):
            link = quote(str(x))
            text = str(x).split(os.sep)[-1]
            try:
                isfile = x.is_file()
            except Exception as e:
                isfile = True
            if isfile:
                vid = False
                vid_ext = ['avi', 'mp4', 'mkv', 'ogv', 'ogg', 'flv', 'm4v',
                           'mov', 'mpg', 'mpeg', 'wmv']
                if text.split('.')[-1] in vid_ext:
                    vid = True
                listing.append(
                    '<li><a class="{cls}" href="/?play={link}">{text}</a></li>'.format(
                        cls=('video' if vid else 'file'), link=link, text=text))
            else:
                listing.append(
                    '<li><a class="folder" href="/?dir={link}/">{text}/</a></li>'.format(
                        link=link, text=text))
        listing.append('</ul>')

        self.respond_ok((self.base + ''.join(listing)).encode())

    def play_file(self, fpath):
        kill_mpv = dict(
            nt='taskkill /f /im mpv.exe',
            posix='killall -9 mpv'
            )
        call(kill_mpv[os.name], shell=True)
        def call_mpv(fpath):
            call(['mpv', '--lua=commandbridge.lua', '--fs', '--force-window', fpath])
        Thread(target=call_mpv, args=(fpath,)).start()
        self.redirect('/control')

    def do_GET(self):

        qs_list = dict(parse_qsl(urlparse(self.path).query))
        dir_path = qs_list.get('dir')
        play_path = qs_list.get('play')
        control_command = qs_list.get('control')

        if dir_path:
            if dir_path == 'WINROOT' and os.name == 'nt':
                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in map(chr, range(65, 91)):
                    if bitmask & 1:
                        drives.append(letter)
                    bitmask >>= 1
                drive_link = '<a href="/?dir={drive}%3A/">{drive}:</a>'
                drive_links = [drive_link.format(drive=d) for d in drives]
                self.respond_ok('<br>'.join(drive_links).encode())
            else:
                self.list_dir(dir_path)
        elif play_path:
            self.play_file(play_path)
        elif control_command in self.commands:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(self.commands[control_command], ('localhost', 9876))
            h = 1
            if control_command == 'stop': h = 2
            self.respond_ok('<script>history.go(-{});</script>'.format(h).encode())
        elif self.path == '/control':
            self.respond_ok(self.controls.encode())
        elif self.path == '/':
            homedir = expanduser('~')
            self.redirect('/?dir='+quote(homedir))
        else:
            self.respond_notfound()

if __name__ == '__main__':
    srv = HTTPServer(('', 9876), MpvRequestHandler)
    srv.serve_forever()
