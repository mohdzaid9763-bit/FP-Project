// Modern delete confirmation modal
function showConfirm(message, href) {
    var modal = document.getElementById('confirmModal');
    var msgEl = document.getElementById('confirmMessage');
    var ok = document.getElementById('confirmOk');
    var cancel = document.getElementById('confirmCancel');

    msgEl.textContent = message;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    // focus the cancel button to avoid accidental confirms
    cancel.focus();

    function cleanup() {
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        ok.removeEventListener('click', onOk);
        cancel.removeEventListener('click', onCancel);
        document.removeEventListener('keydown', onKey);
    }

    function onOk() { cleanup(); window.location.href = href; }
    function onCancel() { cleanup(); }
    function onKey(e) { if (e.key === 'Escape') onCancel(); }

    ok.addEventListener('click', onOk);
    cancel.addEventListener('click', onCancel);
    document.addEventListener('keydown', onKey);
}

// Intercept clicks on .btn-delete and show modal
document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.btn-delete');
    if (btn) {
        e.preventDefault();
        var href = btn.href;
        var item = btn.getAttribute('data-item') || 'this item';
        showConfirm('Delete "' + item + '"? This action cannot be undone.', href);
    }
});

// Auto-hide flash messages and support close button
document.addEventListener('DOMContentLoaded', function () {
    // Theme handling: apply persisted theme or system preference
    (function () {
        var stored = localStorage.getItem('theme');
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        var useDark = stored === 'dark' || (stored === null && prefersDark);
        if (useDark) {
            document.documentElement.classList.add('dark');
        }
        var btn = document.getElementById('themeToggle');
        if (btn) {
            var initialIsDark = document.documentElement.classList.contains('dark');
            btn.textContent = initialIsDark ? '☀️' : '🌙';
            btn.setAttribute('aria-pressed', initialIsDark ? 'true' : 'false');
            btn.setAttribute('aria-label', initialIsDark ? 'Switch to light mode' : 'Switch to dark mode');
            btn.addEventListener('click', function () {
                var isDark = document.documentElement.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
                btn.textContent = isDark ? '☀️' : '🌙';
                btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
                btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            });
        }
    })();

    var messages = document.querySelectorAll('.msg');
    messages.forEach(function (msg) {
        // Close button
        var closeBtn = msg.querySelector('.msg-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                msg.style.display = 'none';
            });
        }

        // Show entrance animation
        msg.style.transform = 'translateY(6px) scale(0.98)';
        msg.style.opacity = '0';
        setTimeout(function () {
            msg.style.opacity = '1';
            msg.style.transform = 'translateY(0) scale(1)';
        }, 40);

        // Confetti on success/info
        if (msg.classList.contains('success') || msg.classList.contains('info')) {
            // spawn confetti near message
            var rect = msg.getBoundingClientRect();
            spawnConfetti(rect.left + rect.width / 2, rect.top + rect.height / 2);
        }

        // Auto-hide after 5 seconds
        setTimeout(function () {
            if (msg && msg.style.display !== 'none') {
                msg.style.opacity = '0';
                setTimeout(function () {
                    msg.style.display = 'none';
                }, 300);
            }
        }, 5000);
    });

    // Notification bell dropdown toggle
    var bell = document.getElementById('notificationBell');
    var dropdown = document.getElementById('notificationsDropdown');
    if (bell && dropdown) {
        bell.addEventListener('click', function (e) {
            e.stopPropagation();
            dropdown.classList.toggle('open');
        });

        document.addEventListener('click', function () {
            dropdown.classList.remove('open');
        });

        dropdown.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    }

    // Chart.js dashboard bar chart (with fallback)
    var chartCanvas = document.getElementById('dashboardChart');
    var fallbackEl = document.getElementById('dashboardBarChart');
    function buildFallbackBarChart(el) {
        // previous manual bar layout as graceful fallback
        el.innerHTML = '';
        var data = {
            students: parseInt(el.dataset.students || '0', 10),
            teachers: parseInt(el.dataset.teachers || '0', 10),
            classes: parseInt(el.dataset.classes || '0', 10),
            attendance: parseInt(el.dataset.attendance || '0', 10),
            notices: parseInt(el.dataset.notices || '0', 10)
        };

        var max = Math.max(data.students, data.teachers, data.classes, data.attendance, data.notices, 1);
        var maxBarHeight = 150;
        var items = [
            { key: 'students', label: 'Students', css: 'bar-students' },
            { key: 'teachers', label: 'Teachers', css: 'bar-teachers' },
            { key: 'classes', label: 'Classes', css: 'bar-classes' },
            { key: 'attendance', label: 'Attendance', css: 'bar-attendance' },
            { key: 'notices', label: 'Notices', css: 'bar-notices' }
        ];

        items.forEach(function (item) {
            var value = data[item.key] || 0;
            var heightPx = (value / max) * maxBarHeight;

            var wrapper = document.createElement('div');
            wrapper.className = 'bar-item';

            var bar = document.createElement('div');
            bar.className = 'bar-fill ' + item.css;
            bar.style.height = heightPx + 'px';

            var valueLabel = document.createElement('div');
            valueLabel.className = 'bar-value';
            valueLabel.textContent = value;

            var label = document.createElement('div');
            label.className = 'bar-label';
            label.textContent = item.label;

            wrapper.appendChild(bar);
            wrapper.appendChild(valueLabel);
            wrapper.appendChild(label);
            el.appendChild(wrapper);
        });
    }

    if (chartCanvas && window.Chart) {
        // read data
        var students = parseInt(chartCanvas.dataset.students || '0', 10);
        var teachers = parseInt(chartCanvas.dataset.teachers || '0', 10);
        var classes = parseInt(chartCanvas.dataset.classes || '0', 10);
        var attendance = parseInt(chartCanvas.dataset.attendance || '0', 10);
        var notices = parseInt(chartCanvas.dataset.notices || '0', 10);

        var labels = ['Students', 'Teachers', 'Classes', 'Attendance', 'Notices'];
        var values = [students, teachers, classes, attendance, notices];

        var rootStyle = getComputedStyle(document.documentElement);
        var colorStudents = rootStyle.getPropertyValue('--bar-students').trim() || '#4facfe';
        var colorTeachers = rootStyle.getPropertyValue('--bar-teachers').trim() || '#43e97b';
        var colorClasses = rootStyle.getPropertyValue('--bar-classes').trim() || '#fa709a';
        var colorAttendance = rootStyle.getPropertyValue('--bar-attendance').trim() || '#a18cd1';
        var colorNotices = rootStyle.getPropertyValue('--bar-notices').trim() || '#fbc2eb';

        // prepare gradients
        var ctx = chartCanvas.getContext('2d');
        function makeGradient(color) {
            try {
                var g = ctx.createLinearGradient(0, 0, 0, chartCanvas.height || 260);
                g.addColorStop(0, color);
                g.addColorStop(1, color + '99');
                return g;
            } catch (e) {
                return color;
            }
        }

        var bg = [makeGradient(colorStudents), makeGradient(colorTeachers), makeGradient(colorClasses), makeGradient(colorAttendance), makeGradient(colorNotices)];

        // create chart
        try {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Counts',
                        data: values,
                        backgroundColor: bg,
                        borderRadius: 8,
                        barPercentage: 0.6,
                        categoryPercentage: 0.7
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: true }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--muted') || '#666' } },
                        y: { beginAtZero: true, ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--muted') || '#666' } }
                    }
                }
            });
        } catch (e) {
            // fallback to manual bars
            console.warn('Chart.js rendering failed, falling back to simple bars', e);
            if (fallbackEl) { fallbackEl.style.display = ''; buildFallbackBarChart(fallbackEl); }
            if (chartCanvas) { chartCanvas.style.display = 'none'; }
        }
    } else if (fallbackEl) {
        // Chart.js not available — show fallback
        if (chartCanvas) { chartCanvas.style.display = 'none'; }
        fallbackEl.style.display = '';
        buildFallbackBarChart(fallbackEl);
    }

    // Role toggle on auth forms (login page)
    var roleToggle = document.querySelectorAll('.role-toggle .btn-role');
    var roleInput = document.getElementById('roleInput');
    if (roleToggle && roleToggle.length && roleInput) {
        roleToggle.forEach(function (btn) {
            btn.addEventListener('click', function () {
                roleToggle.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                roleInput.value = btn.getAttribute('data-role') || 'student';
            });
        });
    }

    // --- Confetti / party helpers ---
    function spawnConfetti(x, y, count = 28) {
        // Suppress confetti on landing-clean pages (keeps landing minimal)
        if (document.body.classList.contains('landing-clean') || document.documentElement.classList.contains('landing-clean')) { return; }
        var container = document.createElement('div');
        container.className = 'confetti-container';
        container.style.position = 'absolute';
        container.style.left = (x - 10) + 'px';
        container.style.top = (y - 10) + 'px';
        document.body.appendChild(container);

        for (var i = 0; i < count; i++) {
            (function () {
                var el = document.createElement('div');
                el.className = 'confetti';
                var colors = ['#ff5f6d','#ffc371','#7ee8fa','#b388ff','#ffd166'];
                var color = colors[Math.floor(Math.random()*colors.length)];
                el.style.background = color;
                el.style.left = (Math.random()*40 - 20) + 'px';
                el.style.top = '0px';
                el.style.opacity = '1';
                el.style.transform = 'rotate(' + (Math.random()*360) + 'deg)';
                container.appendChild(el);
                setTimeout(function () {
                    el.style.top = (120 + Math.random()*360) + 'px';
                    el.style.left = (parseFloat(el.style.left) + (Math.random()*200 - 100)) + 'px';
                    el.style.opacity = '0';
                }, 25 + Math.random()*120);
            })();
        }

        setTimeout(function () { container.remove(); }, 2400);
    }

    // party toggle: toggles very-crazy UI
    var partyBtn = document.getElementById('partyToggle');
    (function () {
        // Do not enable party mode on the clean landing page
        if (document.body.classList.contains('landing-clean') || document.documentElement.classList.contains('landing-clean')) {
            if (partyBtn) partyBtn.style.display = 'none';
            return;
        }
        var stored = localStorage.getItem('party') === 'on';
        if (stored) document.documentElement.classList.add('party');
        if (partyBtn) {
            partyBtn.setAttribute('aria-pressed', document.documentElement.classList.contains('party') ? 'true' : 'false');
            partyBtn.addEventListener('click', function () {
                var isOn = document.documentElement.classList.toggle('party');
                localStorage.setItem('party', isOn ? 'on' : 'off');
                partyBtn.setAttribute('aria-pressed', isOn ? 'true' : 'false');
            });
        }
    })();

    // Features dropdown: toggle on click, support keyboard, close on outside click
    document.querySelectorAll('.nav-drop-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            var parent = btn.closest('.nav-dropdown');
            var isOpen = parent.classList.toggle('open');
            btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            e.stopPropagation();
            if (isOpen) {
                // Move focus to first menu item for keyboard users
                var first = parent.querySelector('.dropdown-menu a');
                if (first) first.focus();
            }
        });
        btn.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); btn.click(); } });
    });

    document.addEventListener('click', function (e) {
        document.querySelectorAll('.nav-dropdown.open').forEach(function (d) {
            if (!d.contains(e.target)) {
                d.classList.remove('open');
                var b = d.querySelector('.nav-drop-btn'); if (b) b.setAttribute('aria-expanded', 'false');
            }
        });
    });

    // Close dropdowns on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.nav-dropdown.open').forEach(function (d) {
                d.classList.remove('open');
                var b = d.querySelector('.nav-drop-btn'); if (b) b.setAttribute('aria-expanded', 'false');
            });
        }
    });

    // Smooth scroll for local anchor links beginning with '#'
    document.addEventListener('click', function (e) {
        var a = e.target.closest && e.target.closest('a[href^="#"]');
        if (!a) return;
        var hash = a.getAttribute('href');
        if (!hash || hash === '#') return;
        var el = document.querySelector(hash);
        if (el) {
            e.preventDefault();
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            history.pushState && history.pushState(null, '', hash);
        }
    });

    // logout sparkle + confetti (graceful delay so user sees the effect)
    var logoutBtn = document.querySelector('.btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function (e) {
            // prevent immediate navigation so animation is visible
            e.preventDefault();
            var href = logoutBtn.href;
            spawnConfetti(e.pageX, e.pageY, 14);
            // small timeout to let the effect play, then continue navigation
            setTimeout(function () { window.location.href = href; }, 220);
        });
    }

    // small click sparkle
    document.addEventListener('click', function (e) {
        var s = document.createElement('div');
        s.className = 'click-sparkle';
        s.style.left = e.pageX + 'px';
        s.style.top = e.pageY + 'px';
        document.body.appendChild(s);
        setTimeout(function () { s.remove(); }, 800);
    });

});
