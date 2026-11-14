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
// Roxora Imager's page: the Hero's Download button becomes the package
// for the system this browser runs on. Nothing is sent anywhere; the
// browser already says what it runs on. Where it does not say (a phone, an
// unknown system) the button keeps pointing at the list of every package.
(function () {
  var source = document.getElementById('imager-offer');
  var get = document.getElementById('imager-get');
  if (!source || !get) return;
  var offer = JSON.parse(source.textContent);
  var uaData = navigator.userAgentData;
  var ua = navigator.userAgent || '';
  var name = ((uaData && uaData.platform) || navigator.platform || '').toLowerCase();
  var mobile = (uaData && uaData.mobile) || /android|iphone|ipad|ipod/i.test(ua) ||
    (name.indexOf('mac') === 0 && navigator.maxTouchPoints > 1);
  var system = mobile ? '' : name.indexOf('win') === 0 ? 'windows' :
    name.indexOf('mac') === 0 ? 'macos' : /linux|x11/.test(name) ? 'linux' : '';
  var mine = system && offer[system];
  if (!mine) return;

  function show(arch) {
    var pick = mine[arch] || mine[Object.keys(mine)[0]];
    get.href = pick.url;
    get.classList.add('download-link');
    get.querySelector('.pf-v6-c-button__text').textContent = pick.text;
    var what = document.getElementById('imager-what');
    what.textContent = pick.what + '. ';
    what.hidden = false;
  }
  // A Mac reports Intel whatever it has, so Apple silicon, which every Mac
  // sold since 2020 has, is offered unless the browser says otherwise.
  var arm = /aarch64|arm64|armv8/i.test(ua + ' ' + (navigator.platform || ''));
  show(system === 'macos' ? 'arm64' : system === 'windows' ? 'x64' : arm ? 'arm64' : 'x86_64');
  document.getElementById('imager-all').hidden = false;
  if (uaData && uaData.getHighEntropyValues && system !== 'windows') {
    uaData.getHighEntropyValues(['architecture']).then(function (v) {
      if (v.architecture) show(v.architecture === 'arm' ? 'arm64' : 'x86_64');
    }, function () {});
  }
})();
