#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qsl, quote, unquote
from pathlib import Path
from functools import cmp_to_key
from subprocess import Popen, PIPE
import os
import string
from os.path import expanduser, splitext, dirname, realpath
from base64 import standard_b64encode
import html
import json
mpv_executable = 'mpv'
if os.name == 'nt':
    mpv_executable = 'mpv.com'
script_path = Path(dirname(realpath(__file__)))

def encodeURIComponent(s):
    return quote(s, safe='~()*!.\'')

class MpvProcess(object):
    def __init__(self):
        self.mpv_process = None

class MpvServer(ThreadingMixIn, HTTPServer, MpvProcess):
    pass

class DirectoryViewer(object):

    def __init__(self, path):
        self.path = Path(path)
        self.as_html = '<h1>{nav_links}</h1><hr><ul>{cont_links}</ul>'.format(
                nav_links=self.generate_navigation_links(),
                cont_links=self.generate_content_links(),
            )

    def sort_compare(self, a, b):
        if a.is_dir():
            if b.is_dir():
                return (a.stat().st_mtime < b.stat().st_mtime) - .5
            else:
                return -1
        else:
            if b.is_dir():
                return 1
            else:
                return (str(a).lower() > str(b).lower()) - .5

    def list_directory(self):
        if str(self.path) == 'WINROOT':
            return self.list_windows_drives()
        content = []
        valid_items = []
        for i in self.path.iterdir():
            try:
                if i.exists(): valid_items.append(i)
            except Exception as e:
                print(e)
        for x in sorted(valid_items, key=cmp_to_key(self.sort_compare)):
            if x.parts[-1].startswith('.'): continue
            if x.is_file():
                do = 'play'
                vid_ext = ['avi', 'mp4', 'mkv', 'ogv', 'ogg', 'flv', 'm4v', 'mov', 'mpg', 'mpeg', 'wmv']
                if x.suffix[1:] in vid_ext:
                    filetype = 'video'
                else:
                    filetype = 'file'
            elif x.is_dir():
                do = 'dir'
                filetype = 'folder'
            else: continue
            content.append((str(x), x.parts[-1], do, filetype))

        return content

    def list_windows_drives(self):
        drives = ['{}:\\'.format(letter) for letter in map(chr, range(65, 91))]
        drives = filter(os.path.isdir, drives)
        return [(d, d, 'dir', 'folder') for d in drives]

    def generate_navigation_links(self):
        navlinks = '<a class="navlink" href="/dir?path=WINROOT">(root)</a>|' if os.name == 'nt' else ''
        try:
            navlinks += os.sep.join(
                '<a class="navlink" href="/dir?path={0}">{1}</a>'.format(
                    encodeURIComponent(str(d)), html.escape(d.parts[-1]))
                    for d in list(reversed(self.path.parents)) + [self.path]
                )
        except Exception as e:
            print(e)
        return navlinks

    def generate_content_links(self):
        content = []
        content.append('<li><a class="file" href="/play?path={all}">'
                       '<i class="fa fa-asterisk"></i> (play all)</a></li>'.format(
                            all=encodeURIComponent(str(self.path / '*'))
                        )
                    )
        fa = dict(
            video='fa fa-file-video-o',
            file='',
            folder='fa fa-folder',
            )
        for x in self.list_directory():
            content.append(
                    '<li><a class="{cls}" href="/{do}?path={link}"><i class="{fa}"></i> {text}</a></li>'.format(
                        do=x[2], cls=x[3], fa=fa[x[3]], link=encodeURIComponent(x[0]), text=html.escape(x[1])
                    )
                )
        return ''.join(content)


class Config(object):

    def __init__(self):

        with (script_path / 'template.html').open() as f:
            self.base = string.Template(f.read())
        with (script_path / 'buttons.html').open() as f:
            self.buttons = string.Template(f.read())
        with (script_path / 'commands').open() as f:
            self.commands = dict()
            for c in f.read().splitlines():
                if not c: continue
                cname, command = c.split('=', 1)
                self.commands[cname] = command
        self.config = []
        for conf in [script_path / c for c in ['config', 'mpv.conf']]:
            if not conf.is_file(): continue
            with conf.open() as f:
                self.config += ['--{}'.format(o.strip().split('#', 1)[0])
                                for o in f.read().splitlines()
                                if o and not o.strip().startswith('#')]
        login_file = script_path / 'login'
        if login_file.is_file():
            with login_file.open('rb') as f:
                login = standard_b64encode(f.read().strip())
                self.login = 'Basic {}'.format(login.decode())
        else: self.login = None

config = Config()

class MpvRequestHandler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.1'

    def ask_auth(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="mpv-remote"')
        self.send_header('Content-Length', 0)
        self.end_headers()

    def redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.send_header('Content-Length', 0)
        self.end_headers()

    def respond_ok(self, data=b'', content_type='text/html; charset=utf-8', age=0):
        self.send_response(200)
        self.send_header('Cache-Control', 'public, max-age={}'.format(age))
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def respond_notfound(self, data='404'.encode()):
        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def list_dir(self, path):
        try:
            listing = DirectoryViewer(path).as_html
        except Exception as e:
            return self.respond_notfound(str(e).encode())
        listing = config.base.substitute({'content': '<div class="listing">{}</div>'.format(listing)})
        self.respond_ok(listing.encode())

    def list_dir_files(self, d):
        def _is_file(f):
            try: return f.is_file()
            except: return False
        return [str(f) for f in sorted(d.iterdir(), key=lambda f: str(f).lower()) if _is_file(f)]

    def get_controls(self, play_path):
        parent_dir = Path(play_path).parent
        files = self.list_dir_files(parent_dir)
        try:
            current = files.index(play_path)
        except ValueError:
            current = -1
        playlist = dict(files=files, current=current)
        playlist = 'var playlist = {}'.format(json.dumps(playlist))
        buttons = config.buttons.substitute({'playlist': playlist})
        return config.base.substitute({'content': buttons})

    def play_file(self, fpath):
        try:
            p = self.server.mpv_process
            p.stdin.write(b'quit\n')
            p.stdin.flush()
            p.kill()
        except Exception as e: print(e)
        fpath = Path(fpath)
        if fpath.parts[-1] == '*':
            playlist = self.list_dir_files(fpath.parent)
        else:
            playlist = [str(fpath)]
        cmd = [mpv_executable, '--input-terminal=no', '--input-file=/dev/stdin', '--fs'] + config.config + ['--'] + playlist
        self.server.mpv_process = Popen(cmd, stdin=PIPE)


    def serve_static(self):
        requested = unquote(self.path[len('/static/'):])
        static_dir = script_path / 'static'
        if requested not in os.listdir(str(static_dir)):
            self.respond_notfound('file not found'.encode())
        else:
            try:
                p = static_dir / requested
                with p.open('rb') as f:
                    ct = {'.css': 'text/css'}
                    self.respond_ok(
                        f.read(),
                        (ct.get(splitext(requested)[1]) or 'application/octet-stream'),
                        315360000
                        )
            except Exception as e:
                print(e)
                self.respond_notfound('error reading file'.encode())

    def command_processor(self, command, val):
        if command in ['vol_set', 'seek', 'subdelay', 'audiodelay']:
            try:
                val = float(val)
            except ValueError:
                val = None
        else:
            val = None
        return command, val

    def control_mpv(self, command, val):
        command, val = self.command_processor(command, val)
        try:
            mpv_stdin = self.server.mpv_process.stdin
            mpv_stdin.write((config.commands[command].format(val) + '\n').encode())
            mpv_stdin.flush()
        except Exception as e: print(e)
        self.respond_ok()

    def do_GET(self):

        if config.login:
            if self.headers.get('Authorization') == config.login:
                pass
            else:
                return self.ask_auth()

        url = urlparse(self.path)
        qs_list = dict(parse_qsl(url.query))

        if self.path.startswith('/static/'):
            self.serve_static()
        elif url.path == '/dir' and qs_list.get('path'):
            self.list_dir(qs_list['path'])
        elif url.path == '/play' and qs_list.get('path'):
            play_path = qs_list['path']
            self.play_file(play_path)
            self.respond_ok(self.get_controls(play_path).encode())
        elif url.path == '/control' and qs_list.get('command') in config.commands:
            self.control_mpv(qs_list.get('command'), qs_list.get('val'))
        elif self.path == '/':
            homedir = expanduser('~')
            self.redirect('/dir?path='+encodeURIComponent(homedir))
        else:
            self.respond_notfound()


if __name__ == '__main__':
    srv = MpvServer(('', 9876), MpvRequestHandler)
    srv.serve_forever()
