from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qsl, quote, unquote
from pathlib import Path
from functools import cmp_to_key
from subprocess import call
import os
import string
from os.path import expanduser, splitext, getmtime
from threading import Thread
import socket
if os.name == 'nt': from ctypes import windll

class DirectoryViewer(object):

    def __init__(self, path):
        if path == 'WINROOT' and os.name == 'nt':
            self.as_html = self.list_windows_drives()
        else:
            self.path = Path(path)
            self.as_html = '<h1>{nav_links}</h1><hr><ul>{cont_links}</ul>'.format(
                    nav_links=self.generate_navigation_links(),
                    cont_links=self.generate_content_links(),
                )

    def list_windows_drives(self):
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in map(chr, range(65, 91)):
            if bitmask & 1:
                drives.append(letter)
            bitmask >>= 1
        drive_link = '<li><a class="folder" href="/?dir={drive}%3A%5C"><i class="fa fa-folder"></i> {drive}:</a></li>'
        return '<ul>' + ''.join([drive_link.format(drive=d) for d in drives]) + '</ul>'

    def generate_navigation_links(self):
        navlinks = '<a class="navlink" href="/?dir=WINROOT">(root)</a>|' if os.name == 'nt' else ''
        navlinks += os.sep.join(
            '<a class="navlink" href="/?dir={0}">{1}</a>'.format(
                quote(str(d)), d.parts[-1])
                for d in list(reversed(self.path.parents)) + [self.path]
            )
        return navlinks

    def sort_compare(self, a, b):
        def two_files(c, d): return (str(c).lower() > str(d).lower()) - .5
        try:
            a.is_dir()
            b.is_dir()
        except Exception as e:
            print(e)
            return two_files(a, b)
        if a.is_dir():
            if b.is_dir():
                return (getmtime(str(a)) < getmtime(str(b))) - .5
            else:
                return -1
        elif a.is_file():
            if b.is_file():
                return two_files(a, b)
            else:
                return 1
        else:
            return two_files(a, b)

    def generate_content_links(self):
        content = []
        for x in sorted(self.path.iterdir(), key=cmp_to_key(self.sort_compare)):
            text = str(x).split(os.sep)[-1]
            if text.startswith('.'): continue
            link = quote(str(x))
            try:
                isfile = x.is_file()
                isdir = x.is_dir()
            except Exception as e:
                continue
            if isfile:
                function = 'play'
                vid = False
                vid_ext = ['avi', 'mp4', 'mkv', 'ogv', 'ogg', 'flv', 'm4v',
                           'mov', 'mpg', 'mpeg', 'wmv']
                if splitext(text)[1][1:] in vid_ext:
                    vid = True
                if vid:
                    cls = 'video'
                    fa = 'fa fa-file-video-o'
                else:
                    cls = 'file'
                    fa = ''
            elif isdir:
                function = 'dir'
                cls = 'folder'
                fa = 'fa fa-folder'
            else:
                continue
            content.append(
                    '<li><a class="{cls}" href="/?{function}={link}"><i class="{fa}"></i> {text}</a></li>'.format(
                        function=function, cls=cls, fa=fa, link=link, text=text
                    )
                )
        return ''.join(content)


class MpvRequestHandler(BaseHTTPRequestHandler):

    with open('template.html', 'r') as f: base = string.Template(f.read())
    with open('buttons.html', 'r') as f: buttons = f.read()
    with open('allowed', 'r') as f:
        commands = dict()
        for c in f.read().splitlines():
            if not c: continue
            cname, command = c.split('=', 1)
            if command.startswith('file='):
                with open(command[len('file='):], 'r') as sf:
                    command = sf.read()
            commands[cname] = command
    with open('config', 'r') as f:
        config = ['--{}'.format(o) for o in f.read().splitlines()
                  if '=' in o and not o.startswith('#')]

    controls = { 'content': buttons }
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
        try:
            listing = DirectoryViewer(path).as_html
        except Exception as e:
            return self.respond_notfound(str(e).encode())
        listing = self.base.substitute({'content': '<div class="listing">{}</div>'.format(listing)})
        self.respond_ok(listing.encode())

    def play_file(self, fpath):
        kill_mpv = dict(
            nt='taskkill /f /im mpv.exe',
            posix='killall -9 mpv'
            )
        call(kill_mpv[os.name], shell=True)
        def call_mpv(fpath):
            call(['mpv', '--lua=commandbridge.lua'] + self.config + ['--', fpath])
        Thread(target=call_mpv, args=(fpath,)).start()
        self.redirect('/control')

    def serve_static(self):
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

    def control_mpv(self, command):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(command.encode(), ('localhost', 9876))
        h = 1
        if command == 'mp.command("stop")': h = 2
        self.respond_ok('<script>history.go(-{});</script>'.format(h).encode())

    def do_GET(self):

        qs_list = dict(parse_qsl(urlparse(self.path).query))
        dir_path = qs_list.get('dir')
        play_path = qs_list.get('play')
        control_command = qs_list.get('control')

        if self.path.startswith('/static/'):
            self.serve_static()
        elif dir_path:
            self.list_dir(dir_path)
        elif play_path:
            self.play_file(play_path)
        elif control_command in self.commands:
            self.control_mpv(self.commands[control_command])
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
