(function() {
    var vol = ('; ' + document.cookie).match(/; volume=(.*?)(;|$)/);
    if (vol) {
        document.getElementById('vol').value = vol[1];
    }
}());

function set_filename () {
    var filename;
    if (playlist['current'] >= 0 && playlist['current'] < playlist['files'].length) {
        filename = playlist['files'][playlist['current']].split(/[\\/]/).pop();
    }
    else if (playlist['current'] == -1) {
        filename = '*';
    }
    document.getElementById('filename').innerHTML = filename;
}
set_filename();

function set_and_save_volume () {
    var vol = document.getElementById('vol').value;
    document.cookie = 'volume=' + vol + '; max-age=31536000; ';
    xhr_get('/control?command=vol_set&val=' + vol);
}

function xhr_get (path, onready) {
    if (!onready) {
        onready = function(){};
    }
    var req = new XMLHttpRequest();
    req.onreadystatechange = function () {
        if (req.readyState == 4 && req.status == 200) {
            onready();
        }
    }
    req.open("GET", path, true);
    req.send();
}

window.pressed = false;
window.pressed_buttons = {};

function press (path, onready) {
    release(path);
    window.pressed_buttons[path + '_timeout'] = setTimeout(function() {
        var interval_id = setInterval(function() {
            if (!window.pressed) {
                clearInterval(interval_id);
            }
            else {
                xhr_get(path, onready);
            }
        }, 50);
        window.pressed_buttons[path + '_interval'] = interval_id;
    }, 500);
}

function release (path) {
    clearTimeout(pressed_buttons[path + '_timeout']);
    clearInterval(pressed_buttons[path + '_interval']);
}

var controls = document.getElementsByClassName('control');
for (var i = 0; i < controls.length; i++) {
    (function() {
        var c = controls[i];
        var p = c.getAttribute('controlpath');
        var onready = eval('(function () {' + c.getAttribute('onready') + '})');
        c.addEventListener('click', function() {xhr_get(p, onready)}, false);
    }());
}


var is_touch = 'ontouchstart' in window;

if (is_touch) {
    window.addEventListener('touchstart', function() {window.pressed = true}, false);
    window.addEventListener('touchend', function() {window.pressed = false}, false);
    window.addEventListener('orientationchange', function() {window.pressed = false}, false);
}
else {
    window.addEventListener('mousedown', function(){window.pressed = true}, false);
    window.addEventListener('mouseup', function(){window.pressed = false}, false);
}

var repeating_controls = document.getElementsByClassName('repeat');

for (var i = 0; i < repeating_controls.length; i++) {
    (function() {
        var c = repeating_controls[i];
        var p = c.getAttribute('controlpath');
        var onready = eval('(function () {' + c.getAttribute('onready') + '})');
        if (is_touch) {
            c.addEventListener('touchstart', function() {press(p, onready)}, false);
            c.addEventListener('touchend', function() {release(p)}, false);
        }
        else {
            c.addEventListener('mousedown', function() {press(p, onready)}, false);
            c.addEventListener('mouseup', function() {release(p)}, false);
        }
    }());
}

function playlist_go (step) {
    var previous = playlist['current'];
    if (previous == -1) {
        if (step == 1)
            xhr_get('/control?command=pl_next');
        else if (step == -1)
            xhr_get('/control?command=pl_prev');
    }
    else if (previous + step >= 0 && previous + step < playlist['files'].length) {
        playlist['current'] = previous + step;
        var file = playlist['files'][playlist['current']];
        var play_query = '/play?path=' + encodeURIComponent(file);
        xhr_get(play_query, function() {
            window.history.replaceState('', '', play_query);
            set_filename();
        });
    }
}

var prev = document.getElementById('pl_prev');
var next = document.getElementById('pl_next');
prev.addEventListener('click', function() {playlist_go(-1)}, false);
next.addEventListener('click', function() {playlist_go(1)}, false);
