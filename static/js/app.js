/* ==========================================================================
   NeuroScan AI – Shared frontend helpers (window.NS)
   ========================================================================== */

(function (window) {
    'use strict';

    var TOKEN_KEY = 'neuroscan_token';
    var USER_KEY = 'neuroscan_user';

    var CLASS_LABELS = {
        glioma: 'Glioma',
        meningioma: 'Meningioma',
        notumor: 'No tumor',
        pituitary: 'Pituitary',
        other: 'Other'
    };

    /* ------------------------------------------------------------- Text escaping */
    function esc(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /* ------------------------------------------------------------- Formatters */
    function className(key) {
        if (!key) return '';
        var lower = String(key).toLowerCase();
        if (CLASS_LABELS[lower]) return CLASS_LABELS[lower];
        return lower.charAt(0).toUpperCase() + lower.slice(1);
    }

    function fmtPct(val) {
        var num = Number(val);
        if (isNaN(num)) return '0%';
        return (num * 100).toFixed(1) + '%';
    }

    function fmtDate(isoString) {
        if (!isoString) return '–';
        try {
            var d = new Date(isoString);
            if (isNaN(d.getTime())) return String(isoString);
            return d.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return String(isoString);
        }
    }

    

    function distHtml(probabilities, predictedClass) {
        if (!probabilities) return '';
        return Object.keys(probabilities).map(function (key) {
            var val = Number(probabilities[key]) || 0;
            var pct = (val * 100).toFixed(1);
            var isTop = (key === predictedClass);
            return '<div class="dist-row c-' + esc(key) + (isTop ? ' is-top' : '') + '">' +
                '<div class="dist-label"><i></i>' + esc(className(key)) + '</div>' +
                '<div class="dist-track"><div class="dist-fill" style="--w:0%" data-w="' + pct + '%"></div></div>' +
                '<div class="dist-value">' + pct + '%</div>' +
                '</div>';
        }).join('');
    }

    function animateBars(container) {
        if (!container) return;
        requestAnimationFrame(function () {
            var fills = container.querySelectorAll('.dist-fill[data-w]');
            fills.forEach(function (fill) {
                fill.style.setProperty('--w', fill.getAttribute('data-w'));
            });
        });
    }

    /* --------------------------------------------------- Alerts and loading state */
    function showAlert(el, message, type) {
        if (!el) return;
        el.className = 'alert alert-' + (type || 'info');
        el.textContent = message;
        el.hidden = false;
    }

    function hideAlert(el) {
        if (!el) return;
        el.hidden = true;
        el.textContent = '';
    }

    function setLoading(button, isLoading, text) {
        if (!button) return;
        if (isLoading) {
            button._origHtml = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<span class="spinner" aria-hidden="true"></span> ' + esc(text || 'Loading…');
        } else {
            button.disabled = false;
            if (button._origHtml !== undefined) {
                button.innerHTML = button._origHtml;
            }
        }
    }

    /* --------------------------------------------------------------------- Toast */
    function toast(message, type) {
        var stack = document.querySelector('.toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'toast-stack';
            document.body.appendChild(stack);
        }

        var item = document.createElement('div');
        item.className = 'toast' + (type ? ' toast-' + type : '');
        item.textContent = message;
        stack.appendChild(item);

        setTimeout(function () {
            item.style.transition = 'opacity .25s, transform .25s';
            item.style.opacity = '0';
            item.style.transform = 'translateY(8px)';
            setTimeout(function () {
                if (item.parentNode) item.parentNode.removeChild(item);
            }, 250);
        }, 4000);
    }

    /* ----------------------------------------------------------------- Modal & Dialog */
    function openModal(contentNode, opts) {
        opts = opts || {};
        var backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';

        var modal = document.createElement('div');
        modal.className = 'modal' + (opts.wide ? ' modal-wide' : '');
        modal.appendChild(contentNode);
        backdrop.appendChild(modal);

        document.body.appendChild(backdrop);
        document.body.classList.add('modal-open');

        requestAnimationFrame(function () {
            backdrop.classList.add('show');
        });

        var closed = false;
        function close() {
            if (closed) return;
            closed = true;
            backdrop.classList.remove('show');
            document.removeEventListener('keydown', onKeyDown);
            setTimeout(function () {
                if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
                if (!document.querySelector('.modal-backdrop')) {
                    document.body.classList.remove('modal-open');
                }
                if (typeof opts.onClose === 'function') {
                    opts.onClose();
                }
            }, 200);
        }

        function onKeyDown(e) {
            if (e.key === 'Escape') close();
        }
        document.addEventListener('keydown', onKeyDown);

        backdrop.addEventListener('click', function (e) {
            if (e.target === backdrop) close();
        });

        return { close: close, element: modal };
    }

    function dialog(opts) {
        opts = opts || {};
        return new Promise(function (resolve) {
            var wrap = document.createElement('div');
            var inputHtml = '';
            if (opts.input) {
                inputHtml =
                    '<div class="field">' +
                    '<label for="dlgInput">' + esc(opts.input.label || '') + '</label>' +
                    '<textarea class="input textarea" id="dlgInput" placeholder="' + esc(opts.input.placeholder || '') +
                    '" maxlength="' + (opts.input.maxlength || 300) + '" rows="3"></textarea>' +
                    '</div>';
            }

            wrap.innerHTML =
                '<h3>' + esc(opts.title || 'Are you sure?') + '</h3>' +
                '<p class="modal-msg">' + esc(opts.message || '') + '</p>' +
                inputHtml +
                '<div class="modal-actions">' +
                '<button class="btn btn-ghost" type="button" data-dlg-cancel>Cancel</button>' +
                '<button class="btn ' + (opts.danger ? 'btn-danger' : 'btn-primary') + '" type="button" data-dlg-confirm>' +
                esc(opts.confirmText || 'Confirm') +
                '</button>' +
                '</div>';

            var resolved = false;
            var handle = openModal(wrap, {
                onClose: function () {
                    if (!resolved) {
                        resolved = true;
                        resolve(null);
                    }
                }
            });

            var inputEl = wrap.querySelector('#dlgInput');
            if (inputEl) {
                setTimeout(function () { inputEl.focus(); }, 60);
            }

            var cancelBtn = wrap.querySelector('[data-dlg-cancel]');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', function () {
                    if (!resolved) {
                        resolved = true;
                        handle.close();
                        resolve(null);
                    }
                });
            }

            var confirmBtn = wrap.querySelector('[data-dlg-confirm]');
            if (confirmBtn) {
                confirmBtn.addEventListener('click', function () {
                    if (!resolved) {
                        resolved = true;
                        var val = inputEl ? inputEl.value.trim() : '';
                        handle.close();
                        resolve(opts.input ? { value: val } : true);
                    }
                });
            }
        });
    }

    /* ----------------------------------------------------- Session and user storage */
    function getToken() {
        try {
            return localStorage.getItem(TOKEN_KEY) || '';
        } catch (e) {
            return '';
        }
    }

    function getUser() {
        try {
            var raw = localStorage.getItem(USER_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function saveSession(data) {
        if (!data) return;
        try {
            if (data.access_token) localStorage.setItem(TOKEN_KEY, data.access_token);
            localStorage.setItem(USER_KEY, JSON.stringify(data));
        } catch (e) { }
    }

    function clearSession() {
        try {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
        } catch (e) { }
    }

    function isLoggedIn() {
        return Boolean(getToken());
    }

    function homeFor(user) {
        return (user && user.role === 'admin') ? '/admin' : '/doctor';
    }

    function redirectIfLoggedIn() {
        if (isLoggedIn()) {
            location.replace(homeFor(getUser()));
        }
    }

    function requireAuth(expectedRole) {
        if (!isLoggedIn()) {
            location.replace('/login');
            return false;
        }
        var user = getUser();
        if (expectedRole && user && user.role !== expectedRole) {
            location.replace(homeFor(user));
            return false;
        }
        return true;
    }

    function initTopbar() {
        var user = getUser();
        var nameEl = document.getElementById('userName');
        var initialsEl = document.getElementById('userInitials');
        var logoutBtn = document.getElementById('logoutBtn');

        if (user) {
            if (nameEl) nameEl.textContent = user.full_name || user.email || 'User';
            if (initialsEl) {
                var name = (user.full_name || user.email || 'U').trim();
                var parts = name.split(/\s+/);
                var inits = parts.length === 1
                    ? parts[0].slice(0, 2).toUpperCase()
                    : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
                initialsEl.textContent = inits;
            }
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', function () {
                clearSession();
                location.replace('/login');
            });
        }
    }

    /* ------------------------------------------------------------- API fetch wrapper */
    async function api(path, opts) {
        opts = opts || {};
        var headers = Object.assign({}, opts.headers || {});
        if (opts.auth !== false) {
            var token = getToken();
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
        }

        var body = undefined;
        if (opts.json !== undefined) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(opts.json);
        } else if (opts.form !== undefined) {
            body = opts.form;
        } else if (opts.body !== undefined) {
            body = opts.body;
        }

        var response;
        try {
            response = await fetch(path, {
                method: opts.method || 'GET',
                headers: headers,
                body: body
            });
        } catch (netErr) {
            var err = new Error('Could not connect to the server. Please check your network.');
            err.status = 0;
            throw err;
        }

        if (response.status === 401 && opts.auth !== false) {
            clearSession();
            location.replace('/login?expired=1');
            var authErr = new Error('Your session has expired. Please log in again.');
            authErr.status = 401;
            throw authErr;
        }

        if (!response.ok) {
            var errPayload = null;
            try {
                errPayload = await response.json();
            } catch (e) { }

            var msg = 'Request failed (' + response.status + ')';
            if (errPayload) {
                if (typeof errPayload.detail === 'string') {
                    msg = errPayload.detail;
                } else if (Array.isArray(errPayload.detail)) {
                    msg = errPayload.detail.map(function (item) { return item.msg; }).join(', ');
                } else if (errPayload.message) {
                    msg = errPayload.message;
                }
            }

            var apiErr = new Error(msg);
            apiErr.status = response.status;
            apiErr.data = errPayload;
            throw apiErr;
        }

        if (opts.blob) {
            return await response.blob();
        }
        if (response.status === 204) {
            return null;
        }
        return await response.json();
    }

    /* ------------------------------------------------------- Interactive UI listeners */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-toggle-password]');
        if (!btn) return;
        var wrap = btn.closest('.input-wrap');
        if (!wrap) return;
        var input = wrap.querySelector('input');
        if (!input) return;
        var isPass = input.type === 'password';
        input.type = isPass ? 'text' : 'password';
        btn.textContent = isPass ? 'Hide' : 'Show';
        btn.setAttribute('aria-pressed', isPass ? 'true' : 'false');
    });

    /* -------------------------------------------------------------- Export namespace */
    window.NS = {
        esc: esc,
        className: className,
        fmtPct: fmtPct,
        fmtDate: fmtDate,
        distHtml: distHtml,
        animateBars: animateBars,
        showAlert: showAlert,
        hideAlert: hideAlert,
        setLoading: setLoading,
        toast: toast,
        openModal: openModal,
        dialog: dialog,
        getToken: getToken,
        getUser: getUser,
        saveSession: saveSession,
        clearSession: clearSession,
        isLoggedIn: isLoggedIn,
        homeFor: homeFor,
        redirectIfLoggedIn: redirectIfLoggedIn,
        requireAuth: requireAuth,
        initTopbar: initTopbar,
        api: api
    };
})(window);
