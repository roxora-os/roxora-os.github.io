/*
 * Copyright (C) 2026 Jiaxing Hu <gahing@gahingwoo.com>
 *
 * This program is free software; you can redistribute it and/or modify it under
 * the terms of the GNU General Public License version 2 as published by the
 * Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program; if not, see <https://www.gnu.org/licenses/>.
 */
// The Download page's chooser: board, then Ubuntu version, desktop and
// kernel, then the one file. The markup and the data (the JSON in
// #download-data) come from tools/page_download.py; this file only shows,
// hides and fills. The choice is kept in the address, nowhere else, so a
// link to it can be shared and nothing is stored on the device.
(function () {
  var source = document.getElementById('download-data');
  var boardCard = document.getElementById('board');
  if (!source || !boardCard) return;
  var data = JSON.parse(source.textContent);
  function $(id) { return document.getElementById(id); }

  // The choices after the board, in the order they are asked. Each lists
  // its values with the default first, as the page's data has them.
  var DIMS = ['release', 'ubuntu', 'flavor', 'kernel'];
  var order = {
    release: data.releases.map(function (r) { return r.tag; }),
    ubuntu: data.ubuntus.map(function (u) { return u[0]; }),
    flavor: data.flavors.map(function (f) { return f[0]; }),
    kernel: data.kernels
  };
  var state = { board: null, release: null, ubuntu: null, flavor: null, kernel: null };
  // Choices the visitor can see for the board; the address names only those.
  var shown = {};

  function release(tag) {
    return data.releases.filter(function (r) { return r.tag === tag; })[0];
  }
  function board(id) {
    return data.boards.filter(function (b) { return b.id === id; })[0];
  }
  function nameOf(dim, value, pool) {
    if (dim === 'release') { var r = release(value); return r.version + (r.beta ? ' beta' : ''); }
    if (dim === 'ubuntu') return data.ubuntus.filter(function (u) { return u[0] === value; })[0][1];
    if (dim === 'flavor') return data.flavors.filter(function (f) { return f[0] === value; })[0][1];
    var img = pool.filter(function (i) { return i.kernel === value; })[0];
    return value + ', Linux ' + img.kernelVersion;
  }

  // ---- step 1: the board ----
  var rows = Array.prototype.slice.call(document.querySelectorAll('#board-table tbody tr'));
  function collapseBoard(on) {
    boardCard.classList.toggle('is-collapsed', on);
  }
  function chooseBoard(id) {
    if (!board(id)) return false;
    state.board = id;
    rows.forEach(function (tr) {
      var on = tr.getAttribute('data-board') === id;
      tr.classList.toggle('pf-m-selected', on);
      tr.querySelector('input').checked = on;
    });
    var b = board(id);
    $('board-summary').textContent = b.name + ', ' + b.soc;
    collapseBoard(true);
    update();
    return true;
  }
  rows.forEach(function (tr) {
    tr.addEventListener('click', function () { chooseBoard(tr.getAttribute('data-board')); });
    tr.querySelector('input').addEventListener('change', function () {
      chooseBoard(tr.getAttribute('data-board'));
    });
  });
  $('board-change').addEventListener('click', function () {
    collapseBoard(false);
    $('board-search').focus();
  });

  // ---- step 2: the image ----
  function renderChoice(dim, values, pool) {
    var box = $('choice-' + dim);
    var group = box.querySelector('.pf-v6-c-toggle-group');
    shown[dim] = values.length > 1;
    box.hidden = !shown[dim];
    group.textContent = '';
    if (!shown[dim]) return;
    values.forEach(function (value) {
      var item = document.createElement('div');
      item.className = 'pf-v6-c-toggle-group__item';
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'pf-v6-c-toggle-group__button' + (state[dim] === value ? ' pf-m-selected' : '');
      button.setAttribute('aria-pressed', state[dim] === value ? 'true' : 'false');
      var text = document.createElement('span');
      text.className = 'pf-v6-c-toggle-group__text';
      text.textContent = nameOf(dim, value, pool);
      button.appendChild(text);
      button.addEventListener('click', function () {
        state[dim] = value;
        update();
        // The buttons were drawn again; keep the keyboard where it was.
        var again = group.querySelector('[aria-pressed="true"]');
        if (again) again.focus();
      });
      item.appendChild(button);
      group.appendChild(item);
    });
  }

  // Walks the choices in order. Each offers the values the board has given
  // the choices before it, and one that no longer fits falls back to the
  // default, the first value.
  function resolve() {
    var pool = data.images.filter(function (i) { return i.board === state.board; });
    DIMS.forEach(function (dim) {
      var values = order[dim].filter(function (v) {
        return pool.some(function (i) { return i[dim] === v; });
      });
      if (values.indexOf(state[dim]) < 0) state[dim] = values[0];
      renderChoice(dim, values, pool);
      pool = pool.filter(function (i) { return i[dim] === state[dim]; });
    });
    return pool[0];
  }

  // ---- step 3: the file ----
  function label(text, cls) {
    var outer = document.createElement('span');
    outer.className = 'pf-v6-c-label pf-m-compact ' + cls;
    var content = document.createElement('span');
    content.className = 'pf-v6-c-label__content';
    var inner = document.createElement('span');
    inner.className = 'pf-v6-c-label__text';
    inner.textContent = text;
    content.appendChild(inner);
    outer.appendChild(content);
    return outer;
  }
  function link(id, href, text) {
    var a = $(id);
    a.href = href;
    if (text !== undefined) a.textContent = text;
  }

  function show(img) {
    var rel = release(img.release);
    var b = board(img.board);
    $('dl-name').textContent = 'Roxora ' + rel.version + ' for ' + b.name;
    $('dl-sub').textContent = 'Ubuntu ' + img.ubuntuName + ' (' + img.codename + '), ' +
      img.flavorName + ', ' + img.kernel + ' kernel ' + img.kernelVersion;
    var labels = $('dl-labels');
    labels.textContent = '';
    if (rel.beta) labels.appendChild(label('Beta', 'pf-m-orange'));
    $('dl-beta').hidden = !rel.beta;

    $('dl-spi').hidden = !img.spi;
    if (img.spi) {
      link('dl-spi-link', img.spi.url, img.spi.file);
      $('dl-spi-size').textContent = img.spi.size;
      $('dl-spi-sha').textContent = img.spi.sha256;
      link('dl-spi-more', '/boards/#' + img.board);
    }
    $('dl-uefi').hidden = !img.uefi;
    if (img.uefi) link('dl-uefi-more', '/boards/#' + img.board);

    link('dl-button', img.url);
    $('dl-size').textContent = img.size + ' to download, ' + img.written + ' on the card';
    link('dl-file', img.url, img.file);
    $('dl-sha').textContent = img.sha256;
    $('dl-release').textContent = 'Roxora ' + rel.version + (rel.beta ? ' beta' : '') + ', ' + rel.date;
    link('dl-notes', rel.url);
    $('dl-verify-wrap').hidden = !img.verify;
    if (img.verify) link('dl-verify', img.verify);

    Array.prototype.forEach.call(document.querySelectorAll('[data-file]'), function (el) {
      el.textContent = img.file;
    });
  }

  function address(img) {
    var q = ['board=' + encodeURIComponent(img.board), 'ubuntu=' + encodeURIComponent(img.ubuntu)];
    if (shown.flavor || img.flavor !== order.flavor[0]) q.push('flavor=' + encodeURIComponent(img.flavor));
    if (shown.kernel || img.kernel !== order.kernel[0]) q.push('kernel=' + encodeURIComponent(img.kernel));
    if (img.release !== order.release[0]) q.push('release=' + encodeURIComponent(release(img.release).version));
    return location.pathname + '?' + q.join('&');
  }

  function update() {
    var img = resolve();
    var any = DIMS.some(function (dim) { return shown[dim]; });
    $('image').hidden = !img || !any;
    $('result').hidden = !img;
    if (!img) return;
    show(img);
    try { history.replaceState(null, '', address(img)); } catch (e) {}
  }

  // ---- a choice named by the address ----
  function fromAddress() {
    // The old page's anchors: #image-<board>-<codename>-<branch>.
    var hash = location.hash.slice(1);
    var named = hash && data.images.filter(function (i) { return i.anchor === hash; })[0];
    if (named) {
      DIMS.forEach(function (dim) { state[dim] = named[dim]; });
      return named.board;
    }
    var q = new URLSearchParams(location.search);
    var want = q.get('ubuntu');
    if (want) {
      var img = data.images.filter(function (i) { return i.ubuntu === want || i.codename === want; })[0];
      if (img) state.ubuntu = img.ubuntu;
    }
    if (q.get('flavor')) state.flavor = q.get('flavor');
    if (q.get('kernel')) state.kernel = q.get('kernel');
    want = q.get('release');
    if (want) {
      var rel = data.releases.filter(function (r) {
        return r.version === want || r.tag === want || (want === 'beta' && r.beta);
      })[0];
      if (rel) state.release = rel.tag;
    }
    return q.get('board');
  }

  var first = fromAddress();
  if (first) chooseBoard(first);
})();
