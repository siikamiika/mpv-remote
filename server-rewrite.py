#!/usr/bin/env python3

from lib import *
from pathlib import Path
import os
from os.path import dirname, realpath
import json

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

class FolderContent(object):

    def __init__(self, path):
        self.path = Path(path)
        if str(path) == 'WINROOT':
            self.content = self._list_windows_drives()
        else:
            self.content = []
            for item in self.path.iterdir():
                i = self._item_info(item)
                if i: self.content.append(i)

    def as_json(self):
        return json.dumps(dict(
            path=self.path.parts,
            content=self.content,
            sep=os.sep
            ))

    def _item_info(self, item):
        try:
            _ = item.stat()
        except Exception as e:
            print(e)
            return
        return dict(
            path=item.parts,
            type='dir' if item.is_dir() else 'file',
            modified=_.st_mtime,
            size=_.st_size
            )

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
        except Exception as e: print(e)
        fpath = Path(fpath)
        conf_path = fpath.parent / 'mpv-remote.conf'
        folder_config = ['--{}'.format(c) for c in
                conf_path.open().read().splitlines()
                if re.match('((secondary-)?(a|s|v)(id|lang)|(sub|audio)(-delay))=[0-9a-z\.\-]+$', c)
            ] if conf_path.is_file() else []
        if fpath.parts[-1] == '*':
            playlist = self.list_dir_files(fpath.parent)
        else:
            playlist = [str(fpath)]
        cmd = [mpv_executable, '--input-terminal=no', '--input-file=/dev/stdin', '--fs'] 
        cmd += config.mpv_config() + folder_config + ['--'] + playlist
        self.server.mpv_process = Popen(cmd, stdin=PIPE)

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
    config = Config(script_path / 'preferences')
    srv = MpvServer(('', 9876), MpvRequestHandler)
    srv.serve_forever()