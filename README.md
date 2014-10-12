# mpv-remote

## Deployment

### Basic

Should work by running `python3 server.py` if you have mpv installed. On
Windows this means having `mpv.com` in your PATH or mpv-remote files all over
the mpv directory.

### Configuration

To set a password against unauthorized LAN access or CSRF, create a file
called `./login` containing `username:password`.


You can add mpv-remote specific mpv configurations, such as `fs-screen=1` or `force-window=yes` to files `./config` or `./mpv.conf`.
Both files will be loaded and appended to mpv command line.

## Usage

Open http://example:9876 on your smartphone and you will be redirected to your
home directory. Navigate to media files and click to play them on your HTPC.
