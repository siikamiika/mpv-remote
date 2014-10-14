(function() {
    var vol = ('; ' + document.cookie).match(/; volume=(.*?)(;|$)/);
    if (vol) {
        document.getElementById('vol').value = vol[1];
    }
}());

function set_and_save_volume () {
    var vol = document.getElementById('vol').value;
    document.cookie = 'volume=' + vol + '; max-age=31536000; ';
    xhr_get('/control?command=vol_set&val=' + vol);
}

function xhr_get (path, onready) {
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
        var onready = eval('(function () {' + c.getAttribute('onready') + '})')
        c.addEventListener('click', function() {xhr_get(p, onready)}, false);
    }());
}


var is_touch = 'ontouchstart' in window

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
        var onready = eval('(function () {' + c.getAttribute('onready') + '})')
        if (is_touch) {
            c.addEventListener('touchstart', function() {press(p, onready)}, false);
        }
        else {
            c.addEventListener('mousedown', function() {press(p, onready)}, false);
        }
    }());
}
