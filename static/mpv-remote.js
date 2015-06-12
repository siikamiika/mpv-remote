function xhr (type, path, data, onready, cachebusting, async) {
    if (!(cachebusting === false)) var cachebusting = true;
    if (type == 'POST') var cachebusting = false;
    if (!(async === false)) var async = true;
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
    req.open(type, path + (cachebusting ? sessionStorage.cachebuster : ''), async);
    req.send(data);
}

function encode_state(state) {
    return [state, '#' + encodeURIComponent(JSON.stringify(state))];
}

function init_playlist (path) {
    var playlist_folder = JSON.stringify(path.slice(0, -1));
    var playlist_index_key = playlist_folder + 'playlist_index';
    var playlist = JSON.parse(localStorage.getItem(playlist_folder));
    var playlist_index = -1;
    for (var i = 0; i < playlist.length; i++) {
        if (playlist[i] === path[path.length - 1]) {
            playlist_index = i;
            break
        }
    }
    localStorage.setItem(playlist_index_key, playlist_index);
}

function play_file (path, first, ytdl) {
    var playpath = path;
    var url = '/play'
    if (ytdl) {
        playpath = path[path.length - 1];
        url = '/ytdl_play';
    }
    xhr('POST', url, JSON.stringify(playpath), function() {
        show_controls(path);
        if (first)
            init_playlist(path);
    });
}

function playlist_go (step) {
    var ytdl = false;
    var play_type = 'play_file';
    if (history.state.show_controls[0] == 'YTDL') {
        ytdl = true;
        play_type = 'ytdl_play';
    }
    var playlist_folder = history.state.show_controls.slice(0, -1);
    var playlist_folder_str = JSON.stringify(playlist_folder);
    var new_value = parseInt(JSON.parse(localStorage.getItem(playlist_folder_str + 'playlist_index'))) + step;
    var playlist_files = JSON.parse(localStorage.getItem(playlist_folder_str));
    if (new_value > -1 && new_value < playlist_files.length) {
        localStorage.setItem(playlist_folder_str + 'playlist_index', new_value);
        var filename = playlist_folder.concat(playlist_files[new_value]);
        var state = {};
        state[play_type] = filename;
        state = encode_state(state);
        history.replaceState(state[0], '', state[1]);
        play_file(filename, false, ytdl);
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
        var state = encode_state({'show_controls': path});
        history.replaceState(state[0], '', state[1]);
        document.getElementById('content').innerHTML = buttons_html;
        document.getElementById('filename').innerHTML = path[path.length - 1];
        var vol = localStorage.volume;
        if (vol)
            document.getElementById('vol').value = JSON.parse(vol);
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
        document.getElementById('replay').addEventListener('click', function(e) {
            playlist_go(0);
        })
    });
}

function control_mpv (command, val, onready) {
    if (!val) val = undefined;
    xhr('POST', '/control', JSON.stringify({'command': command, 'val': val}), onready);
}

function set_and_save_volume () {
    var vol = document.getElementById('vol').value;
    localStorage.volume = vol;
    control_mpv('vol_set', vol);
}

// function cookie (action, name, data) {
//     if (action == 'load') {
//         var pattern = new RegExp('; '+ name + '=(.*?)(;|$)');
//         var match = ('; ' + document.cookie).match(pattern);
//         if (match)
//             return match[1];
//         else
//             return '';
//     }
//     else if (action == 'save') {
//         document.cookie = name + '=' + data + '; max-age=31536000; '
//     }
// }

function toggle_sorting (item) {
    var sorting = JSON.parse(localStorage.sorting);
    function toggle (index, val1, val2) {
        sorting[index] = sorting[index] == val1 ? val2 : val1;
    }
    if (item == 'filefoldersort') {
        toggle(0, 'file', 'folder');
    }
    else if (item == 'foldersort-mode') {
        toggle(1, 'modified', 'name');
    }
    else if (item == 'foldersort-order') {
        toggle(2, 'asc', 'desc');
    }
    else if (item == 'filesort-mode') {
        toggle(3, 'modified', 'name');
    }
    else if (item == 'filesort-order') {
        toggle(4, 'asc', 'desc');
    }
    localStorage.sorting = JSON.stringify(sorting);
    var state = window.location.hash.substring(1);
    state = decodeURIComponent(state);
    state = JSON.parse(state);
    open_folder(state.open_folder);
}

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

function show_folder_content (content_json, file_dir_order, dirsort, dirsort_order, filesort, filesort_order) {
    // file_dir_order: 'file' or 'folder' (which first)
    // dirsort and filesort: 'modified' or 'name'
    // order for dirsort and filesort: 'asc' or 'desc'
    var contentlinks = document.getElementById('contentlinks');
    var files = [];
    var folders = [];
    var ytdl_playlists = [];
    for (var i = 0; i < content_json.content.length; i++) {
        if (content_json.content[i].type == 'dir') {
            folders.push(content_json.content[i]);
        }
        else if (content_json.content[i].type == 'file') {
            files.push(content_json.content[i]);
        }
        else if (content_json.content[i].type == 'ytdl_playlist') {
            ytdl_playlists.push(content_json.content[i]);
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
            var path = item.path[item.path.length - 1];
            var contentlink = document.createElement('a');
            contentlink.className = 'contentlink';
            if (item.type == 'dir') {
                var state = encode_state({'open_folder': item.path});
                activate_link(contentlink, state);
                var iconclass = 'fa fa-folder';
                var pathclass = 'folder';
            }
            else if (item.type == 'file') {
                var state = encode_state({'play_file': item.path});
                activate_link(contentlink, state);
                var vid_ext = ['avi', 'mp4', 'mkv', 'ogv', 'ogg', 'flv', 'm4v', 'mov', 'mpg', 'mpeg', 'wmv', 'm3u', 'm3u8'];
                var ext = path.split('.').pop();
                if (vid_ext.indexOf(ext) > -1) {
                    var iconclass = 'fa fa-file-video-o';
                    var pathclass = 'video';
                }
                else {
                    var iconclass = 'fa fa-file-o';
                    var pathclass = 'file';
                }
            }
            var modified = new Date(item.modified * 1000).toLocaleString();
            contentlink.innerHTML = ('<i class="{0}"></i><span class="{1}">{2}</span><br>'+
                                    '<span class="modified">{3}</span>').format(iconclass, pathclass, path, modified);
            var li = document.createElement('li');
            li.appendChild(contentlink);
            contentlinks.appendChild(li);
        }());
    }
    for (var i = 0; i < ytdl_playlists.length; i++) {
        var contentlink = document.createElement('a');
        var state = encode_state({'ytdl_playlist': ytdl_playlists[i].path});
        activate_link(contentlink, state);
        var pathclass = 'ytdl-playlist';
        contentlink.className = 'contentlink';
        contentlink.innerHTML = '<span class="{0}">{1}</span>'.format(pathclass, ytdl_playlists[i].path);
        var li = document.createElement('li');
        li.appendChild(contentlink);
        contentlinks.appendChild(li);
    }
    var sorting = JSON.parse(localStorage.sorting);
    var icons = {
        'file': 'fa-file-o',
        'folder': 'fa-folder',
        'modified': 'fa-clock-o',
        'name': 'fa-sort-alpha-asc',
        'asc': 'fa-sort-amount-asc',
        'desc': 'fa-sort-amount-desc'
    }
    var sort_controls = [];
    sort_controls.push(document.getElementById('filefoldersort'));
    sort_controls.push(document.getElementById('foldersort-mode'));
    sort_controls.push(document.getElementById('foldersort-order'));
    sort_controls.push(document.getElementById('filesort-mode'));
    sort_controls.push(document.getElementById('filesort-order'));
    for (var i = 0; i < sort_controls.length; i++) {
        (function () {
            var icon = document.createElement('i');
            icon.className = 'fa fa-2x '+icons[sorting[i]];
            sort_controls[i].appendChild(icon);
            var id = sort_controls[i].id;
            sort_controls[i].addEventListener('click', function (){
                toggle_sorting(id);
            });
        }());
    }
    document.getElementById('sortbuttons').style.visibility = 'visible';
    var playlist_files = [];
    for (var i = 0; i < files.length; i++) {
        playlist_files.push(files[i].path[files[i].path.length - 1]);
    }
    localStorage.setItem(JSON.stringify(content_json.path), JSON.stringify(playlist_files));
}

function show_navigation_links (parts) {
    var navlinks = document.getElementById('navlinks');
    function create_navlink(text, path, top, _unclickable) {
        var navlink = document.createElement('a');
        navlink.className = 'navlink';
        if (top) navlink.className += ' top';
        navlink.innerHTML = text;
        if (!_unclickable) {
            var state = encode_state({'open_folder': path});
            activate_link(navlink, state);
        }
        navlinks.appendChild(navlink);
    }
    create_navlink('YTDL', ['YTDL'], true);
    create_navlink('ROOT', [window.os == 'nt' ? 'WINROOT' : '/'], true);
    var unclickable = false;
    if (parts[0] == 'YTDL')
        unclickable = true;
    for (var i = 0; i < parts.length; i++) {
        create_navlink(parts[i], parts.slice(0, i+1), false, unclickable);
    }
}

function open_folder (path) {
    xhr('GET', '/static/browser.html', null, function (browser_html) {
        document.getElementById('content').innerHTML = browser_html;
        xhr('POST', '/dir', JSON.stringify(path), function (dircontent_json){
            dircontent_json = JSON.parse(dircontent_json);
            show_navigation_links(dircontent_json.path);
            var sorting = localStorage.sorting;
            if (!sorting) {
                sorting = ['folder', 'modified', 'desc', 'name', 'asc'];
                localStorage.sorting = JSON.stringify(sorting);
            }
            else
                sorting = JSON.parse(sorting);
            var file_dir_order = sorting[0];
            var dirsort = sorting[1];
            var dirsort_order = sorting[2];
            var filesort = sorting[3];
            var filesort_order = sorting[4];
            show_folder_content(dircontent_json, file_dir_order, dirsort, dirsort_order, filesort, filesort_order);
        });
    });
}

function open_ytdl_playlist (url) {
    xhr('GET', '/static/ytdl_browser.html', null, function (browser_html) {
        document.getElementById('content').innerHTML = browser_html;
        xhr('POST', '/ytdl_playlist', JSON.stringify(url), function (playlist_content) {
            playlist_content = JSON.parse(playlist_content);
            show_navigation_links(['YTDL', playlist_content.path]);
            var contentlinks = document.getElementById('contentlinks');
            var playlist_urls = [];
            for (var i = 0; i < playlist_content.content.length; i++) {
                (function () {
                    playlist_urls.push(playlist_content.content[i].url)
                    var contentlink = document.createElement('a');
                    contentlink.className = 'contentlink';
                    contentlink.innerHTML = '<span class="video">{0}</span>'.format(playlist_content.content[i].title);
                    var state = encode_state({'ytdl_play': ['YTDL', playlist_content.path, playlist_content.content[i].url]});
                    activate_link(contentlink, state);
                    var li = document.createElement('li');
                    li.appendChild(contentlink);
                    contentlinks.appendChild(li);
                }());
            }
            localStorage.setItem(JSON.stringify(['YTDL', playlist_content.path]), JSON.stringify(playlist_urls));
        });
    });
}

function open_location (location) {
    if (location.play_file) {
        play_file(location.play_file, true);
    }
    else if (location.open_folder) {
        open_folder(location.open_folder);
    }
    else if (location.show_controls) {
        show_controls(location.show_controls);
    }
    else if (location.ytdl_playlist) {
        open_ytdl_playlist(location.ytdl_playlist);
    }
    else if (location.ytdl_play) {
        play_file(location.ytdl_play, true, true);
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

function reset () {
    sessionStorage.clear();
    localStorage.clear();
}

window.onpopstate = function (e) {
    if (e.state) {
        open_location(e.state);
    }
}

window.onload = function () {
    sessionStorage.cachebuster = '?' + new Date().getTime();
    if (!String.prototype.format) { //http://stackoverflow.com/a/4673436/2444105
      String.prototype.format = function() {
        var args = arguments;
        return this.replace(/{(\d+)}/g, function(match, number) {
          return typeof args[number] != 'undefined'
            ? args[number]
            : match
          ;
        });
      };
    }
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
