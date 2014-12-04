function xhr (type, path, data, onready) {
    loading_indicator(true);
    if (!onready) {
        onready = function(){};
    }
    var req = new XMLHttpRequest();
    req.onreadystatechange = function () {
        if (req.readyState == 4 && req.status == 200) {
            loading_indicator(false);
            onready(req.responseText);
        }
    }
    req.open(type, path, true);
    req.send(data);
}

function encode_state(state) {
    return [state, '#' + encodeURIComponent(JSON.stringify(state))];
}

function play_file (path) {
    xhr('POST', '/play', JSON.stringify(path), function() {
        show_controls(path);
        var playlist_index = window.playlist.files.indexOf(path.join('\\/\\/'));
        if (playlist_index > -1) {
            window.playlist.current = playlist_index;
        }
    });
}

function playlist_go (step) {
    var new_value = window.playlist.current + step;
    if (new_value > -1 && new_value < window.playlist.files.length) {
        window.playlist.current = new_value;
        var filename = window.playlist.files[window.playlist.current].split('\\/\\/');
        play_file(filename);
        var state = encode_state({'play_file': filename});
        history.replaceState(state[0], '', state[1]);
    }
}

function press_button (commands) {
    release_button(commands[0]);
    window.pressed_buttons[commands[0] + '_timeout'] = setTimeout(function() {
        var interval_id = setInterval(function() {
            if (!window.pressed) {
                clearInterval(interval_id);
            }
            else {
                control_mpv(commands[0], commands[1], commands[2]);
            }
        }, 50);
        window.pressed_buttons[commands[0] + '_interval'] = interval_id;
    }, 500);
}

function release_button (commands) {
    clearTimeout(pressed_buttons[commands[0] + '_timeout']);
    clearInterval(pressed_buttons[commands[0] + '_interval']);
}

function activate_control (c, repeat) {
    var commands = c.getAttribute('control').split('|');
    var command = commands[0];
    var val = commands[1];
    var onready = (function() {eval(commands[2])});
    if (!repeat) {
        c.addEventListener('click', function(e) {
            e.preventDefault();
            control_mpv(command, val, onready);
        }, false);
    }
    else {
        if ('ontouchstart' in window) {
            c.addEventListener('touchstart', function() {press_button(commands)}, false);
            c.addEventListener('touchend', function() {release_button(commands)}, false);
        }
        else {
            c.addEventListener('mousedown', function() {press_button(commands)}, false);
            c.addEventListener('mouseup', function() {release_button(commands)}, false);
        }
    }
}

function show_controls (path) {
    xhr('GET', '/static/buttons.html', null, function (buttons_html){
        document.getElementById('content').innerHTML = buttons_html;
        document.getElementById('filename').innerHTML = path[path.length - 1];
        var vol = ('; ' + document.cookie).match(/; volume=(.*?)(;|$)/);
        if (vol)
            document.getElementById('vol').value = vol[1];
        var controls = document.getElementsByClassName('control');
        for (var i = 0; i < controls.length; i++) {
            activate_control(controls[i]);
        }
        var repeating_controls = document.getElementsByClassName('repeat');
        for (var i = 0; i < repeating_controls.length; i++) {
            activate_control(repeating_controls[i], true);
        }
        document.getElementById('pl_prev').addEventListener('click', function(e) {
            playlist_go(-1);
        }, false);
        document.getElementById('pl_next').addEventListener('click', function(e) {
            playlist_go(1);
        }, false);
    });
}

function control_mpv (command, val, onready) {
    xhr('POST', '/control', JSON.stringify({'command': command, 'val': val}), onready);
}

function set_and_save_volume () {
    var vol = document.getElementById('vol').value;
    document.cookie = 'volume=' + vol + '; max-age=31536000; ';
    control_mpv('vol_set', vol);
}

function show_folder_content (content, file_dir_order, dirsort, dirsort_order, filesort, filesort_order) {
    // file_dir_order: 'file' or 'folder' (which first)
    // dirsort and filesort: 'modified' or 'name'
    // order for dirsort and filesort: 'asc' or 'desc'
    var contentlinks = document.getElementById('contentlinks');
    function compare_fn (attribute, order) {
        return (function (a,b) {
            if (order == 'asc') {}
            else if (order == 'desc') {
                var tmp = a;
                a = b;
                b = tmp;
            }
            var cmp_a, cmp_b;
            if (attribute == 'name') {
                cmp_a = a.path[a.path.length - 1].toLowerCase();
                cmp_b = b.path[b.path.length - 1].toLowerCase();
            }
            else if (attribute == 'modified') {
                cmp_a = a.modified;
                cmp_b = b.modified;
            }
            if (cmp_a < cmp_b)
                return -1;
            else if (cmp_a > cmp_b)
                return 1;
            else
                return 0;
        });
    }
    var files = [];
    var folders = [];
    for (var i = 0; i < content.length; i++) {
        if (content[i].type == 'dir') {
            folders.push(content[i]);
        }
        else if (content[i].type == 'file') {
            files.push(content[i]);
        }
    }
    files.sort(compare_fn(filesort, filesort_order));
    folders.sort(compare_fn(dirsort, dirsort_order));
    var items = [files, folders];
    if (file_dir_order == 'folder')
        items = items.reverse();
    items = items[0].concat(items[1]);
    for (var i = 0; i < items.length; i++) {
        (function() {
            var item = items[i];
            var filename = item.path[item.path.length - 1];
            var contentlink = document.createElement('a');
            var icon = document.createElement('i');
            if (item.type == 'dir') {
                var state = encode_state({'open_folder': item.path});
                activate_link(contentlink, state);
                icon.className = 'fa fa-folder';
                contentlink.className = 'folder';
            }
            else if (item.type == 'file') {
                var state = encode_state({'play_file': item.path});
                activate_link(contentlink, state);
                var vid_ext = ['avi', 'mp4', 'mkv', 'ogv', 'ogg', 'flv', 'm4v', 'mov', 'mpg', 'mpeg', 'wmv'];
                var ext = filename.split('.').pop();
                if (vid_ext.indexOf(ext) > -1) {
                    icon.className = 'fa fa-file-video-o';
                    contentlink.className = 'video';
                }
                else {
                    contentlink.className = 'file';
                }
            }
            contentlink.appendChild(icon);
            contentlink.appendChild(document.createTextNode(' ' + filename));
            var li = document.createElement('li');
            li.appendChild(contentlink);
            contentlinks.appendChild(li);
        }());
    }
    window.playlist = {'files': [], 'current': -1};
    for (var i = 0; i < files.length; i++) {
        window.playlist.files.push(files[i].path.join('\\/\\/'));
    }
}

function show_navigation_links (parts) {
    var navlinks = document.getElementById('navlinks');
    if (window.os == 'nt') {
        var winroot = document.createElement('a');
        winroot.className = 'navlink';
        winroot.innerHTML = '(root)';
        var state = encode_state({'open_folder': ['WINROOT']});
        activate_link(winroot, state);
        navlinks.appendChild(winroot);
    }
    for (var i = 0; i < parts.length; i++) {
        (function() {
            var navlink = document.createElement('a');
            var link = parts.slice(0, i+1);
            var state = encode_state({'open_folder': link});
            activate_link(navlink, state);
            navlink.className = 'navlink';
            navlink.innerHTML = parts[i];
            navlinks.appendChild(navlink);
        }());
    }
}

function open_folder (path) {
    xhr('GET', '/static/browser.html', null, function (browser_html) {
        document.getElementById('content').innerHTML = browser_html;
        xhr('POST', '/dir', JSON.stringify(path), function (dircontent_json){
            dircontent_json = JSON.parse(dircontent_json);
            show_navigation_links(dircontent_json.path);
            show_folder_content(dircontent_json.content, 'folder', 'modified', 'desc', 'name', 'asc');
        });
    });
}

function open_location (location) {
    if (location.play_file) {
        play_file(location.play_file);
    }
    else if (location.open_folder) {
        open_folder(location.open_folder);
    }
    else if (location.show_controls) {
        show_controls(location.show_controls);
    }
}

function activate_link (element, state, replace_history) {
    element.href = state[1];
    element.addEventListener('click', function(e) {
        e.preventDefault();
        if (replace_history)
            history.replaceState(state[0], '', state[1]);
        else
            history.pushState(state[0], '', state[1]);
        open_location(state[0]);
    }, false);
}

function loading_indicator (on) {
    var indicator = document.getElementById('loading-indicator');
    if (on)
        indicator.style.visibility = 'visible';
    else
        indicator.style.visibility = 'hidden';
}

window.onpopstate = function (e) {
    if (e.state) {
        var state = e.state;
        if (state.play_file) {
            state.show_controls = state.play_file;
            delete state.play_file;
        }
        open_location(state);
    }
}

window.onload = function () {
    xhr('GET', '/prefs', null, function (prefs_json) {
        prefs_json = JSON.parse(prefs_json);
        window.os = prefs_json.os;
        window.home = prefs_json.home;
        window.path_separator = prefs_json.sep;
        if (window.location.hash) {
            var state = window.location.hash.substring(1);
            state = decodeURIComponent(state);
            state = JSON.parse(state);
            open_location(state);
            history.replaceState(state, '');
        }
        else {
            var state = encode_state({'open_folder': window.home});
            open_location(state[0]);
            history.replaceState(state[0], '', state[1]);
        }
    });

    window.pressed = false;
    window.pressed_buttons = {};

    if ('ontouchstart' in window) {
        window.ontouchstart = function () {window.pressed = true};
        window.ontouchend = function () {window.pressed = false};
        window.onorientationchange = function () {window.pressed = false};
    }
    else {
        window.onmousedown = function () {window.pressed = true};
        window.onmouseup = function () {window.pressed = false};
    }
}
