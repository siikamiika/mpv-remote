from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qsl, quote, unquote
from pathlib import Path
from functools import cmp_to_key
from subprocess import call
import os
import string
import json
from os.path import expanduser, splitext
from threading import Thread
import socket
if os.name == 'nt': from ctypes import windll

def lua_fn_str(fn, args):
    return '{}({})'.format(fn, ','.join(['"{}"'.format(a) for a in args]))

class MpvRequestHandler(BaseHTTPRequestHandler):

    with open('template.html', 'r') as f: base = string.Template(f.read())
    with open('layout.json', 'r') as f: layout = json.loads(f.read())

    command_list = []
    for row in layout['layout']:
        for button in row:
            command_list.append(button[1])
    commands = {lua_fn_str(f, a) for f, a in command_list}

    htmlcontrols = '<div class="remote"><div style="text-align:center;">'
    for control in layout['layout']:
        for button in control:
            symbol, command = button
            btn = '<a class="btn" href="/?control={cmd}"><i class="fa fa-3x fa-{sym}"></i></a> '
            htmlcontrols += btn.format(
                cmd=quote(lua_fn_str(command[0], command[1])),
                sym=symbol
                )
        htmlcontrols += '</div><div style="text-align:center;">'
    htmlcontrols += '</div></div>'

    controls = { 'content': htmlcontrols }
    controls = base.substitute(controls)


    def redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()


    def respond_ok(self, data, content_type='text/html; charset=utf-8', age=0):
        self.send_response(200)
        self.send_header('Cache-Control', 'public, max-age={}'.format(age))
        self.send_header('Content-Type', content_type)
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
        parts = [x for x in str(d).split(os.sep) if x]
        nav = '<a class="navlink" href="/?dir={root}">(root)</a>|'.format(
            root='WINROOT' if os.name == 'nt' else '/')
        nav += os.sep.join(
            '<a class="navlink" href="/?dir={0}/">{1}</a>'.format(
                quote(os.sep.join(parts[:i+1])), d_)
                for i, d_ in enumerate(parts)
            )
        listing = ['<h1>{}</h1><hr><ul>'.format(nav)]

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
                if splitext(text)[1][1:] in vid_ext:
                    vid = True
                listing.append(
                    '<li><a class="{cls}" href="/?play={link}"><i class="{fa}"></i> {text}</a></li>'.format(
                        cls=('video' if vid else 'file'), fa=('fa fa-file-video-o' if vid else ''), link=link, text=text))
            else:
                listing.append(
                    '<li><a class="folder" href="/?dir={link}/"><i class="fa fa-folder"></i> {text}/</a></li>'.format(
                        link=link, text=text))
        listing.append('</ul>')
        listing = ''.join(listing)
        listing = self.base.substitute({'content': '<div class="listing">{}</div>'.format(listing)})
        self.respond_ok(listing.encode())

    def play_file(self, fpath):
        kill_mpv = dict(
            nt='taskkill /f /im mpv.exe',
            posix='killall -9 mpv'
            )
        call(kill_mpv[os.name], shell=True)
        def call_mpv(fpath):
            call(['mpv', '--lua=commandbridge.lua', '--fs', fpath])
        Thread(target=call_mpv, args=(fpath,)).start()
        self.redirect('/control')

    def do_GET(self):

        qs_list = dict(parse_qsl(urlparse(self.path).query))
        dir_path = qs_list.get('dir')
        play_path = qs_list.get('play')
        control_command = qs_list.get('control')

        if self.path.startswith('/static/'):
            requested = unquote(self.path[len('/static/'):])
            if requested not in os.listdir('static'):
                self.respond_notfound('file not found'.encode())
            else:
                try:
                    with open('static/'+requested, 'rb') as f:
                        ct = {'.css': 'text/css'}
                        self.respond_ok(
                            f.read(),
                            (ct.get(splitext(requested)[1]) or 'application/octet-stream'),
                            315360000
                            )
                except Exception as e:
                    print(e)
                    self.respond_notfound('error reading file'.encode())
        elif dir_path:
            if dir_path == 'WINROOT' and os.name == 'nt':
                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in map(chr, range(65, 91)):
                    if bitmask & 1:
                        drives.append(letter)
                    bitmask >>= 1
                drive_link = '<li><a class="folder" href="/?dir={drive}%3A/"><i class="fa fa-folder"></i> {drive}:</a></li>'
                drive_links = '<ul>' + ''.join([drive_link.format(drive=d) for d in drives]) + '</ul>'
                listing = self.base.substitute({'content': '<div class="listing">{}</div>'.format(drive_links)})
                self.respond_ok(listing.encode())
            else:
                self.list_dir(dir_path)
        elif play_path:
            self.play_file(play_path)
        elif control_command in self.commands:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(control_command.encode(), ('localhost', 9876))
            h = 1
            if control_command == 'mp.command("stop")': h = 2
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
