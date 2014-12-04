#!/usr/bin/env python3

from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import os
import sys
from os.path import splitext, dirname, realpath, expanduser
import json
import re
from base64 import standard_b64encode
from subprocess import Popen, PIPE, DEVNULL
from urllib.parse import unquote


mpv_executable = 'mpv'
if os.name == 'nt':
    mpv_executable = 'mpv.com'
script_path = Path(dirname(realpath(__file__)))

class Config(object):

    def __init__(self, conf_dir):

        self.dir = conf_dir
        self.commands = dict()
        with (self.dir / 'commands').open() as f:
            for c in f.read().splitlines():
                if not c: continue
                cname, command = c.split('=', 1)
                self.commands[cname] = command

    def mpv_config(self):
        with (self.dir / 'mpv.conf').open() as f:
            return [
                '--{}'.format(o.strip().split('#', 1)[0])
                for o in f.read().splitlines()
                if o and not o.strip().startswith('#')
            ]

    def login(self, auth):
        login_file = self.dir / 'login'
        if login_file.is_file():
            with login_file.open('rb') as f:
                login = standard_b64encode(f.read().strip())
                return auth == 'Basic {}'.format(login.decode())
        else:
            return True

    @staticmethod
    def folder_config(fpath):
        allowed = '((secondary-)?(a|s|v)(id|lang)|(sub|audio)(-delay))=[0-9a-z\.\-]+$'
        fpath = Path(fpath)
        conf_path = fpath.parent / 'mpv-remote.conf'
        return ['--{}'.format(c)
            for c in conf_path.open().read().splitlines()
            if re.match(allowed, c)
        ] if conf_path.is_file() else []


class FolderContent(object):

    def __init__(self, path):
        self.path = Path(path)
        if str(path) == 'WINROOT':
            self.content = self._list_windows_drives()
        else:
            self.content = []
            try:
                for item in self.path.iterdir():
                    i = self._item_info(item)
                    if i: self.content.append(i)
            except Exception as e:
                print(e)

    def as_json(self):
        return json.dumps(dict(
            path=self.path.parts,
            content=self.content
            ))

    def _item_info(self, item):
        try:
            _ = item.stat()
            return dict(
                path=item.parts,
                type='dir' if item.is_dir() else 'file',
                modified=_.st_mtime,
                size=_.st_size
                )
        except Exception as e:
            print(e)
            return

    def _list_windows_drives(self):
        drives = [Path('{}:\\'.format(c)) for c in map(chr, range(65, 91))]
        drives = [self._item_info(d) for d in drives if d.is_dir()]
        return drives


class MpvProcess(object):
    def __init__(self):
        self.mpv_process = None


class MpvServer(ThreadingMixIn, HTTPServer, MpvProcess):
    pass


class MpvRequestHandler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.1'

    def log_message(self, *args, **kwargs):
        if self.command == 'POST':
            if not hasattr(self.server, 'last_logmsg'):
                self.server.last_logmsg = [self.POST_data, 0]
            if self.server.last_logmsg[0] == self.POST_data:
                self.server.last_logmsg[1] += 1
            else:
                self.server.last_logmsg = [self.POST_data, 0]
                sys.stderr.write('\n')
            sys.stderr.write('\r({counter}) {addr} - - [{datetime}] "POST {path} {req_ver}" {statuscode} {data}'.format(
                counter=self.server.last_logmsg[1],
                addr=self.address_string(),
                datetime=self.log_date_time_string(),
                path=self.path,
                req_ver=self.request_version,
                statuscode=args[2],
                data=self.POST_data.decode(),
                ))
            self.server.last_logmsg[0] = self.POST_data
        else:
            BaseHTTPRequestHandler.log_message(self, *args, **kwargs)


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

    def play_file(self, fpath):
        try:
            p = self.server.mpv_process
            p.stdin.write(b'quit\n')
            p.stdin.flush()
            p.kill()
        except: pass
        playlist = [fpath]
        cmd = [mpv_executable, '--input-terminal=no', '--input-file=/dev/stdin', '--fs']
        cmd += config.mpv_config() + config.folder_config(fpath) + ['--'] + playlist
        self.server.mpv_process = Popen(cmd, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)

    def serve_static(self):
        requested = unquote(self.path[len('/static/'):])
        static_dir = script_path / 'static'
        if requested not in os.listdir(str(static_dir)):
            return self.respond_notfound('file not found'.encode())
        try:
            p = static_dir / requested
            with p.open('rb') as f:
                ct = {
                    '.css': 'text/css; charset=utf-8',
                    '.html': 'text/html; charset=utf-8',
                    '.js': 'application/javascript; charset=utf-8'
                    }
                ct = (ct.get(splitext(requested)[1]) or 'application/octet-stream')
                self.respond_ok(
                    data=f.read(),
                    content_type=ct,
                    age=315360000
                    )
        except Exception as e:
            print(e)
            self.respond_notfound('error reading file'.encode())

    def sanitize(self, command, val):
        if command in ['vol_set', 'seek', 'subdelay', 'audiodelay']:
            try:
                val = float(val)
            except ValueError:
                val = None
        else:
            val = None
        return command, val

    def control_mpv(self, command, val):
        command, val = self.sanitize(command, val)
        try:
            mpv_stdin = self.server.mpv_process.stdin
            mpv_stdin.write((config.commands[command].format(val) + '\n').encode())
            mpv_stdin.flush()
        except Exception as e: print(e)

    def do_GET(self):

        if not config.login(self.headers.get('Authorization')):
            return self.ask_auth()

        try:
            if self.path.startswith('/static/'):
                self.serve_static()
            elif self.path == '/':
                index = script_path / 'static' / 'index.html'
                self.respond_ok(index.open('rb').read())
            elif self.path == '/prefs':
                prefs = dict(os=os.name, home=Path(expanduser('~')).parts, sep=os.sep)
                self.respond_ok(json.dumps(prefs).encode(), 'text/plain; charset=utf-8')
            else:
                return self.respond_notfound()
        except Exception as e:
            self.respond_notfound(str(e).encode())

    def do_POST(self):

        if not config.login(self.headers.get('Authorization')):
            return self.ask_auth()

        content_length = int(self.headers.get('Content-Length'))
        self.POST_data = self.rfile.read(content_length)

        try:
            if self.path == '/dir':
                dir_path = os.path.join(*json.loads(self.POST_data.decode()))
                c = FolderContent(dir_path)
                self.respond_ok(c.as_json().encode(), 'application/json')
            elif self.path == '/play':
                file_path = os.path.join(*json.loads(self.POST_data.decode()))
                self.play_file(file_path)
                self.respond_ok()
            elif self.path == '/control':
                command = json.loads(self.POST_data.decode())
                command, val = command.get('command'), command.get('val')
                self.control_mpv(command, val)
                self.respond_ok()
        except Exception as e:
            self.respond_notfound(str(e).encode())


if __name__ == '__main__':
    config = Config(script_path / 'preferences')
    srv = MpvServer(('', 9876), MpvRequestHandler)
    srv.serve_forever()
