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
from subprocess import Popen, PIPE, DEVNULL, check_output
from urllib.parse import unquote, urlparse
from datetime import datetime


mpv_executable = 'mpv'
if os.name == 'nt':
    mpv_executable = 'mpv.com'
script_path = Path(dirname(realpath(__file__)))

class Config(object):

    def __init__(self, conf_dir):

        self.dir = conf_dir
        self.commands = self.mpv_commands()

    def mpv_commands(self):
        commands = dict()
        with (self.dir / 'commands').open() as f:
            for c in f.read().splitlines():
                if not c: continue
                cname, command = c.split('=', 1)
                commands[cname] = command
        return commands

    def mpv_config(self):
        mpv_conf_file = self.dir / 'mpv.conf'
        if not mpv_conf_file.is_file(): return []
        with mpv_conf_file.open() as f:
            return [
                '--{}'.format(o.strip().split('#', 1)[0])
                for o in f.read().splitlines()
                if o and not o.strip().startswith('#')
            ]

    def login(self, auth):
        login_file = self.dir / 'login'
        if not login_file.is_file(): return True
        with login_file.open('rb') as f:
            login = standard_b64encode(f.read().strip())
            return auth == 'Basic {}'.format(login.decode())

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

    def __init__(self, path, config):
        self.path = Path(path)
        self.config = config
        if str(path) == 'WINROOT':
            self._windows_drives()
        elif str(path) == 'YTDL':
            self._ytdl_playlists()
        else:
            self._folder_content()

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

    def _folder_content(self):
        self.content = []
        try:
            for item in self.path.iterdir():
                i = self._item_info(item)
                if i: self.content.append(i)
        except Exception as e:
            print(e)

    def is_drive(self, d):
        try: return d.is_dir()
        except: return False

    def _windows_drives(self):
        drives = [Path('{}:\\'.format(c)) for c in map(chr, range(65, 91))]
        drives = [self._item_info(d) for d in drives if self.is_drive(d)]
        self.content = drives

    def _ytdl_playlists(self):
        ytdl_playlists = self.config.dir / 'ytdl.conf'
        with ytdl_playlists.open() as f:
            self.content = [dict(type='ytdl_playlist', path=url.strip())
                for url in f.read().splitlines() if url.strip()]


class YtdlPlaylistContent(object):

    def __init__(self, url):
        self.url = url
        self._parse_playlist()
        self._get_playlist()

    def as_json(self):
        return json.dumps(dict(
            path=self.url,
            type=self.type,
            content=self.playlist
            ))

    def _detect_site(self):
        sites = [
            ('http?s://(www)?\.youtube\.com', 'youtube'),
            ('http://www.crunchyroll.com', 'crunchyroll'),
            ('http?s://', 'other')
            ]
        for pattern, name in sites:
            if re.search(pattern, self.url):
                return name

    def _get_playlist(self):
        self.type = self._detect_site()
        self.playlist = []
        for url in [e['url'] for e in self.raw_playlist]:
            entry = dict()
            if self.type == 'youtube':
                try:
                    info = json.loads(check_output(['youtube-dl', '-J', url]).decode())
                except Exception as e:
                    print(e)
                    continue
                entry['url'] = 'ytdl://' + url
                entry['date'] =  float(datetime.strptime(info['upload_date'], '%Y%m%d').timestamp())
                entry['length'] = info['duration']
                entry['title'] = info['title']
            elif self.type == 'crunchyroll':
                entry['url'] = url
                entry['title'] = url.split('/')[-1]
            else:
                entry['url'] = url
                entry['title'] = url
            self.playlist.append(entry)


    def _parse_playlist(self):
        ytdl_output = check_output(['youtube-dl', '-J', '--flat-playlist', self.url])
        self.raw_playlist = json.loads(ytdl_output.decode())['entries']




class MpvServer(ThreadingMixIn, HTTPServer):

    def add_config(self, config):
        self.config = config

class MpvRequestHandler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.1'

    def log_message(self, *args, **kwargs):
        if self.command == 'POST':
            sys.stderr.write('{addr} - - [{datetime}] "POST {path} {req_ver}" {statuscode} {data}\n'.format(
                addr=self.address_string(),
                datetime=self.log_date_time_string(),
                path=self.path,
                req_ver=self.request_version,
                statuscode=args[2],
                data=self.POST_data.decode(),
                ))
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

    def play_file(self, fpath, ytdl=False):
        try:
            p = self.server.mpv_process
            p.stdin.write(b'quit\n')
            p.stdin.flush()
            p.kill()
        except: pass
        playlist = [fpath]
        cmd = [mpv_executable, '--input-terminal=no', '--input-file=/dev/stdin', '--fs']
        cmd += self.server.config.mpv_config()
        if ytdl:
            cmd += ['--ytdl']
        else:
            cmd += self.server.config.folder_config(fpath)
        cmd += ['--'] + playlist
        self.server.mpv_process = Popen(cmd, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)

    def serve_static(self):
        requested = unquote(self.url_parsed.path[len('/static/'):])
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
            mpv_stdin.write((self.server.config.commands[command].format(val) + '\n').encode())
            mpv_stdin.flush()
        except Exception as e: print(e)

    def do_GET(self):

        if not self.server.config.login(self.headers.get('Authorization')):
            return self.ask_auth()

        try:
            self.url_parsed = urlparse(self.path)
            if self.url_parsed.path.startswith('/static/'):
                self.serve_static()
            elif self.url_parsed.path == '/':
                index = script_path / 'static' / 'mpv-remote.html'
                self.respond_ok(index.open('rb').read())
            elif self.url_parsed.path == '/prefs':
                prefs = dict(os=os.name, home=Path(expanduser('~')).parts, sep=os.sep)
                self.respond_ok(json.dumps(prefs).encode(), 'text/plain; charset=utf-8')
            else:
                return self.respond_notfound()
        except Exception as e:
            self.respond_notfound(str(e).encode())

    def do_POST(self):

        if not self.server.config.login(self.headers.get('Authorization')):
            return self.ask_auth()

        content_length = int(self.headers.get('Content-Length') or 0)
        self.POST_data = self.rfile.read(content_length)

        try:
            if self.path == '/dir':
                dir_path = os.path.join(*json.loads(self.POST_data.decode()))
                c = FolderContent(dir_path, self.server.config)
                self.respond_ok(c.as_json().encode(), 'application/json')
            elif self.path == '/ytdl_playlist':
                url = json.loads(self.POST_data.decode())
                playlist = YtdlPlaylistContent(url)
                self.respond_ok(playlist.as_json().encode(), 'application/json')
            elif self.path == '/ytdl_play':
                url = json.loads(self.POST_data.decode())
                self.play_file(url, ytdl=True)
                self.respond_ok()
            elif self.path == '/play':
                file_path = os.path.join(*json.loads(self.POST_data.decode()))
                self.play_file(file_path)
                self.respond_ok()
            elif self.path == '/control':
                command = json.loads(self.POST_data.decode())
                command, val = command.get('command'), command.get('val')
                self.control_mpv(command, val)
                self.respond_ok()
            else:
                return self.respond_notfound()
        except Exception as e:
            self.respond_notfound(str(e).encode())


if __name__ == '__main__':
    srv = MpvServer(('', 9876), MpvRequestHandler)
    srv.add_config(Config(script_path / 'preferences'))
    srv.serve_forever()
