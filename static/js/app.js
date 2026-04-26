// ─── CampusConnect Frontend JS ───

// Tab navigation
function showTab(name, el) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    const tab = document.getElementById('tab-' + name);
    if (tab) tab.classList.add('active');
    if (el) el.classList.add('active');
}

// Profile dropdown
function toggleProfileMenu() {
    const dd = document.getElementById('profileDropdown');
    dd.classList.toggle('show');
}

// Close dropdown on outside click
document.addEventListener('click', (e) => {
    const dd = document.getElementById('profileDropdown');
    if (dd && !e.target.closest('.nav-profile-menu')) dd.classList.remove('show');
    const np = document.getElementById('notifPanel');
    if (np && !e.target.closest('#notifBtn') && !e.target.closest('#notifPanel')) np.classList.remove('show');
});

// Notifications
function toggleNotifPanel() {
    document.getElementById('notifPanel').classList.toggle('show');
}

function markAllRead() {
    fetch('/api/notifications/read', { method: 'POST', headers: {'Content-Type':'application/json'} })
        .then(() => {
            document.querySelectorAll('.notif-item').forEach(n => n.classList.remove('unread'));
            const badge = document.getElementById('notifBadge');
            if (badge) badge.style.display = 'none';
        });
}

// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    document.cookie = 'theme=' + next + ';path=/;max-age=31536000';
}

// Flash messages auto-dismiss
document.querySelectorAll('.flash-msg').forEach(msg => {
    setTimeout(() => {
        msg.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => msg.remove(), 300);
    }, 4000);
});

// SocketIO notifications
try {
    const socket = io();
    socket.on('notification', (data) => {
        showToast(data.title, data.message, data.type);
        const badge = document.getElementById('notifBadge');
        if (badge) {
            const count = parseInt(badge.textContent || '0') + 1;
            badge.textContent = count;
            badge.style.display = 'flex';
        }
    });
} catch(e) { /* SocketIO not available */ }

// Toast notification
function showToast(title, message, type = 'info') {
    const container = document.getElementById('flashContainer');
    if (!container) return;
    const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle', badge: 'fa-medal', task: 'fa-tasks' };
    const toast = document.createElement('div');
    toast.className = `flash-msg flash-${type}`;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span><strong>${title}</strong> ${message}</span><i class="fas fa-times flash-close" onclick="this.parentElement.remove()"></i>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.animation = 'slideOut 0.3s ease forwards'; setTimeout(() => toast.remove(), 300); }, 5000);
}

// Smooth number counter animation
function animateNumbers() {
    document.querySelectorAll('.stat-number, .w-stat-num').forEach(el => {
        const text = el.textContent.trim();
        const num = parseInt(text.replace(/[^0-9]/g, ''));
        if (isNaN(num) || num === 0) return;
        const prefix = text.match(/^[^0-9]*/)[0];
        const suffix = text.match(/[^0-9]*$/)[0];
        let current = 0;
        const duration = 1000;
        const step = Math.ceil(num / (duration / 16));
        const timer = setInterval(() => {
            current = Math.min(current + step, num);
            el.textContent = prefix + current.toLocaleString() + suffix;
            if (current >= num) clearInterval(timer);
        }, 16);
    });
}
document.addEventListener('DOMContentLoaded', animateNumbers);

// Mobile sidebar toggle
const sidebar = document.getElementById('sidebar');
if (sidebar) {
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'sidebar-toggle';
    toggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
    toggleBtn.onclick = () => sidebar.classList.toggle('mobile-open');
    const nav = document.querySelector('.navbar');
    if (nav) nav.querySelector('.nav-left').prepend(toggleBtn);
}
