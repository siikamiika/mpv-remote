from urllib.parse import quote

def encodeURIComponent(s):
    return quote(s, safe='~()*!.\'')
