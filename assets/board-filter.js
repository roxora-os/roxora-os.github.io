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
// Search and the vendor filter over a list of boards, shared by the
// Download page's board step and the Boards page. The markup comes from
// board_filter() in tools/markup.py: each board carries data-vendor and
// data-filter, and the element marked data-filter-list is hidden when no
// board matches. Without JavaScript the controls are hidden and the whole
// list shows.
(function () {
  var root = document.querySelector('[data-board-filter]');
  if (!root) return;
  var items = Array.prototype.slice.call(root.querySelectorAll('[data-filter]'));
  var list = root.querySelector('[data-filter-list]');
  var none = document.getElementById('board-none');
  var search = document.getElementById('board-search');
  var vendorSelect = document.getElementById('vendor-select');
  var vendorButtons = Array.prototype.slice.call(root.querySelectorAll('#vendor-list button'));
  var vendor = '';

  function filter() {
    var words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
    var any = false;
    items.forEach(function (el) {
      var hay = el.getAttribute('data-filter');
      var ok = (!vendor || el.getAttribute('data-vendor') === vendor) &&
        words.every(function (w) { return hay.indexOf(w) >= 0; });
      el.hidden = !ok;
      any = any || ok;
    });
    if (list) list.hidden = !any;
    if (none) none.hidden = any;
  }
  function setVendor(v) {
    vendor = v;
    vendorSelect.value = v;
    vendorButtons.forEach(function (b) {
      var on = b.getAttribute('data-vendor') === v;
      b.classList.toggle('pf-m-current', on);
      if (on) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current');
    });
    filter();
  }
  search.addEventListener('input', filter);
  vendorSelect.addEventListener('change', function () { setVendor(vendorSelect.value); });
  vendorButtons.forEach(function (b) {
    b.addEventListener('click', function () { setVendor(b.getAttribute('data-vendor')); });
  });
  filter();
})();
