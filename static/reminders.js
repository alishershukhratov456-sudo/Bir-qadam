/* reminders.js — Eslatma tizimi (Computer local time sync + Browser notifications + Audio Chime + In-app Toast) */
(function () {
  'use strict';

  // ── State ─────────────────────────────────────────────────────────────────
  let reminders = []; // [{id, remind_at, message, fired}]
  let currentFilter = 'all'; // 'all' | 'pending' | 'fired'
  let notifPermission = (typeof window !== 'undefined' && 'Notification' in window)
    ? Notification.permission
    : 'denied';
  let pollTimer = null;
  let clockTimer = null;

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const notifBtn     = document.getElementById('reminder-notif-btn');
  const testBtn      = document.getElementById('reminder-test-btn');
  const quick10sBtn  = document.getElementById('reminder-quick-10s-btn');
  const addBtn       = document.getElementById('add-reminder-btn');
  const msgInput     = document.getElementById('reminder-msg');
  const dtInput      = document.getElementById('reminder-dt');
  const statusEl     = document.getElementById('reminder-form-status');
  const listEl       = document.getElementById('reminders-list');
  const emptyEl      = document.getElementById('reminders-empty');
  const clockEl      = document.getElementById('computer-clock-time');
  const countAllEl   = document.getElementById('count-reminders-all');
  const countPendEl  = document.getElementById('count-reminders-pending');
  const countFiredEl = document.getElementById('count-reminders-fired');
  const filterTabs   = document.querySelectorAll('.reminder-tab-btn');

  // ── Audio Chime (Web Audio API - works on all computers without external files) ─
  function playReminderChime() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      const now = ctx.currentTime;
      // Dual pleasant chime tone
      [
        { freq: 587.33, start: 0, dur: 0.4 },    // D5
        { freq: 880.00, start: 0.15, dur: 0.6 },  // A5
        { freq: 1174.66, start: 0.35, dur: 0.8 }  // D6
      ].forEach(tone => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(tone.freq, now + tone.start);

        gain.gain.setValueAtTime(0.0001, now + tone.start);
        gain.gain.exponentialRampToValueAtTime(0.3, now + tone.start + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + tone.start + tone.dur);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now + tone.start);
        osc.stop(now + tone.start + tone.dur);
      });
    } catch (_) {
      // Audio context may require prior user interaction
    }
  }

  // ── In-App Notification Toast ──────────────────────────────────────────────
  function showToastNotification(message, title) {
    let container = document.getElementById('reminder-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'reminder-toast-container';
      container.className = 'reminder-toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'reminder-toast-card';
    toast.innerHTML = `
      <div class="reminder-toast-icon">🔔</div>
      <div class="reminder-toast-content">
        <strong>${esc(title || 'Eslatma vaqti keldi!')}</strong>
        <p>${esc(message)}</p>
        <small>Kompyuter vaqti: ${new Date().toLocaleTimeString('uz-UZ')}</small>
      </div>
      <button class="reminder-toast-close" type="button" aria-label="Yopish">✕</button>
    `;

    toast.querySelector('.reminder-toast-close').addEventListener('click', () => {
      toast.classList.add('hide');
      setTimeout(() => toast.remove(), 300);
    });

    container.appendChild(toast);

    // Auto dismiss after 10s
    setTimeout(() => {
      if (toast.parentNode) {
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
      }
    }, 10000);
  }

  // ── Computer Clock Real-Time Ticker ────────────────────────────────────────
  function updateComputerClock() {
    if (!clockEl) return;
    const now = new Date();
    const timeStr = now.toLocaleTimeString('uz-UZ', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    clockEl.textContent = timeStr;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function formatDt(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString('uz-UZ', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function getTimeRemainingLabel(isoStr, fired) {
    if (fired) return '✓ Yetkazildi';
    const now = new Date();
    const target = new Date(isoStr);
    const diffMs = target.getTime() - now.getTime();

    if (diffMs <= 0) return '⏰ Vaqti yetdi!';
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `⏳ ${diffSec} soniyadan so'ng`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `⏳ ${diffMin} daqiqadan so'ng`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `⏳ ${diffHrs} soatdan so'ng`;
    const diffDays = Math.floor(diffHrs / 24);
    return `⏳ ${diffDays} kundan so'ng`;
  }

  function setStatus(msg, color) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.style.color = color || '#9999ad';
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, c =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // ── Notification permission ────────────────────────────────────────────────
  function updateNotifBtn() {
    if (!notifBtn) return;
    if (typeof window === 'undefined' || !('Notification' in window)) {
      notifBtn.textContent = '⚠️ Brauzer qo\'llamaydi';
      notifBtn.disabled = true;
      notifBtn.style.opacity = '.6';
      return;
    }

    notifPermission = Notification.permission;
    if (notifPermission === 'granted') {
      notifBtn.innerHTML = '🔔 <span>Bildirishnomalar yoqilgan</span>';
      notifBtn.disabled = false;
      notifBtn.classList.add('btn-success');
    } else if (notifPermission === 'denied') {
      notifBtn.innerHTML = '🔕 <span>Bildirishnoma bloklangan (Sozlamalardan oching)</span>';
      notifBtn.disabled = false;
      notifBtn.classList.remove('btn-success');
    } else {
      notifBtn.innerHTML = '🔔 <span>Bildirishnomaga ruxsat bering</span>';
      notifBtn.disabled = false;
      notifBtn.classList.remove('btn-success');
    }
  }

  if (notifBtn) {
    notifBtn.addEventListener('click', async () => {
      if (!('Notification' in window)) {
        alert("Bu brauzer bildirishnomalarni qo'llab-quvvatlamaydi.");
        return;
      }
      try {
        const result = await Notification.requestPermission();
        notifPermission = result;
        updateNotifBtn();
        if (result === 'granted') {
          playReminderChime();
          new Notification('Yaxshiroq Versiyam ✦', {
            body: "Bildirishnomalar muvaffaqiyatli yoqildi! Kompyuteringiz vaqti bo'yicha eslatmalar yetkaziladi.",
            icon: '/static/favicon.png'
          });
          showToastNotification("Bildirishnomalar yoqildi! Endi belgilangan kompyuter vaqtida sizga eslatma keladi.", "✦ Ruxsat berildi");
        } else {
          showToastNotification("Bildirishnoma brauzerda bloklangan. Sayt sozlamalaridan ruxsat bering.", "Diqqat");
        }
      } catch (err) {
        console.error(err);
      }
    });
  }

  // ── Instant Test Button ────────────────────────────────────────────────────
  if (testBtn) {
    testBtn.addEventListener('click', () => {
      playReminderChime();
      const testMsg = "Bu sinov bildirishnomasi! Kompyuter vaqti: " + new Date().toLocaleTimeString('uz-UZ');
      if (notifPermission === 'granted') {
        new Notification('⏰ Sinov Bildirishnomasi — Bir Qadam', {
          body: testMsg,
          icon: '/static/favicon.png'
        });
      }
      showToastNotification(testMsg, "🔔 Sinov bildirishnomasi");
    });
  }

  // ── Quick 10 Seconds Reminder Button ───────────────────────────────────────
  if (quick10sBtn) {
    quick10sBtn.addEventListener('click', async () => {
      const now = new Date();
      now.setSeconds(now.getSeconds() + 10);
      const pad = n => String(n).padStart(2, '0');
      const timeVal = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
      
      setStatus("10 soniyalik tezkor eslatma yaratilmoqda…");
      try {
        const res = await fetch('/api/reminders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: "⚡ 10 soniya o'tdi! Kichik bir qadam tashlang.",
            remind_at: timeVal
          })
        });
        const data = await res.json();
        if (data.ok) {
          setStatus("✓ 10 soniyalik eslatma qo'shildi! Kompyuteringiz vaqtini kuting.", "#269b76");
          await loadReminders();
        }
      } catch (_) {
        setStatus("Xatolik yuz berdi.", "#c05");
      }
    });
  }

  // ── Render list ───────────────────────────────────────────────────────────
  function renderList() {
    if (!listEl) return;

    // Update counts
    const active = reminders.filter(r => !r.fired);
    const fired  = reminders.filter(r =>  r.fired);

    if (countAllEl)   countAllEl.textContent = reminders.length;
    if (countPendEl)  countPendEl.textContent = active.length;
    if (countFiredEl) countFiredEl.textContent = fired.length;

    // Filter items
    let displayList = [];
    if (currentFilter === 'pending') {
      displayList = active;
    } else if (currentFilter === 'fired') {
      displayList = fired;
    } else {
      // all: pending first, then fired
      displayList = [...active, ...fired];
    }

    // remove old items
    Array.from(listEl.querySelectorAll('.reminder-item')).forEach(el => el.remove());

    if (!displayList.length) {
      if (emptyEl) {
        emptyEl.style.display = '';
        if (currentFilter === 'pending' && fired.length > 0) {
          emptyEl.textContent = "Kutilayotgan faol eslatmalar yo'q. Barcha eslatmalar yakunlangan.";
        } else if (currentFilter === 'fired') {
          emptyEl.textContent = "Hozircha yetkazilgan yoki o'tgan eslatmalar yo'q.";
        } else {
          emptyEl.textContent = "Hozircha eslatmalar yo'q. Yuqoridagi formadan yangi bildirishnoma qo'shing!";
        }
      }
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    displayList.forEach(r => {
      const item = document.createElement('div');
      item.className = 'reminder-item' + (r.fired ? ' fired' : '');
      item.dataset.id = r.id;

      const timeStatus = getTimeRemainingLabel(r.remind_at, r.fired);
      const isPastDue = !r.fired && new Date(r.remind_at) <= new Date();

      item.innerHTML = `
        <div class="reminder-bell ${r.fired ? 'fired' : 'active'}">
          ${r.fired ? '🔕' : '🔔'}
        </div>
        <div class="reminder-body">
          <div class="reminder-body-head">
            <b class="reminder-msg-text">${esc(r.message)}</b>
            <span class="reminder-badge ${r.fired ? 'badge-fired' : (isPastDue ? 'badge-due' : 'badge-pending')}">
              ${timeStatus}
            </span>
          </div>
          <div class="reminder-meta">
            <time title="Belgilangan vaqt">📅 ${formatDt(r.remind_at)}</time>
            <span class="reminder-clock-tag">💻 Kompyuter vaqti</span>
          </div>
        </div>
        <div class="reminder-actions">
          <button class="reminder-delete" data-id="${r.id}" title="O'chirish" aria-label="O'chirish">✕</button>
        </div>
      `;
      listEl.appendChild(item);
    });
  }

  // ── Tab Filters ───────────────────────────────────────────────────────────
  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentFilter = tab.dataset.filter || 'all';
      renderList();
    });
  });

  // ── Fetch reminders from server ───────────────────────────────────────────
  async function loadReminders() {
    try {
      const res = await fetch('/api/reminders');
      if (!res.ok) return;
      reminders = await res.json();
      renderList();
    } catch (_) {}
  }

  // ── Add reminder ──────────────────────────────────────────────────────────
  if (addBtn) {
    addBtn.addEventListener('click', async () => {
      const message   = msgInput ? msgInput.value.trim() : '';
      const remind_at = dtInput ? dtInput.value : ''; // "YYYY-MM-DDTHH:MM"

      if (!message) {
        setStatus("Eslatma matnini kiriting.", '#c05');
        if (msgInput) msgInput.focus();
        return;
      }
      if (!remind_at) {
        setStatus("Sana va vaqtni tanlang.", '#c05');
        if (dtInput) dtInput.focus();
        return;
      }

      // Check computer local time: allow current minute or future
      const targetTime = new Date(remind_at).getTime();
      const nowTime = new Date().getTime();
      // Allow if within last 1 minute grace period or in future
      if (targetTime < nowTime - 60000) {
        setStatus("Belgilangan vaqt o'tib ketgan. Kelajak vaqt tanlang.", '#c05');
        return;
      }

      setStatus('Saqlanmoqda…', '#9999ad');
      try {
        const res = await fetch('/api/reminders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, remind_at })
        });
        const data = await res.json();
        if (data.ok) {
          if (msgInput) msgInput.value = '';
          setMinDatetime();
          setStatus("✓ Bildirishnoma muvaffaqiyatli qo'shildi!", '#269b76');
          await loadReminders();
        } else {
          setStatus(data.error || 'Xatolik yuz berdi.', '#c05');
        }
      } catch (_) {
        setStatus('Tarmoq xatosi. Qayta urinib ko\'ring.', '#c05');
      }
    });
  }

  // ── Delete reminder ───────────────────────────────────────────────────────
  if (listEl) {
    listEl.addEventListener('click', async e => {
      const btn = e.target.closest('.reminder-delete');
      if (!btn) return;
      const id = Number(btn.dataset.id);
      try {
        await fetch(`/api/reminders/${id}`, { method: 'DELETE' });
        reminders = reminders.filter(r => r.id !== id);
        renderList();
      } catch (_) {}
    });
  }

  // ── Polling: check for due reminders every 1 second (Computer clock sync) ──
  function checkDueReminders() {
    const now = new Date();
    updateComputerClock();

    let hasChanges = false;

    reminders.forEach(async r => {
      if (r.fired) return;
      const rTime = new Date(r.remind_at);

      if (rTime <= now) {
        // Mark locally first so it fires exactly once
        r.fired = true;
        hasChanges = true;

        // 1. Play audio chime on computer
        playReminderChime();

        // 2. In-app toast banner
        showToastNotification(r.message, "⏰ Eslatma — Bir Qadam");

        // 3. System / Browser desktop notification
        if (notifPermission === 'granted') {
          try {
            new Notification('⏰ Eslatma — Bir Qadam', {
              body: r.message,
              icon: '/static/favicon.png',
              tag: `reminder-${r.id}`
            });
          } catch (_) {}
        }

        // 4. Update server status
        try {
          await fetch(`/api/reminders/${r.id}/fire`, { method: 'POST' });
        } catch (_) {}
      }
    });

    if (hasChanges) {
      renderList();
    }
  }

  function startPolling() {
    clearInterval(pollTimer);
    checkDueReminders();
    // Check every 1 second for exact computer time matching!
    pollTimer = setInterval(checkDueReminders, 1000);
  }

  // ── Pre-fill datetime-local min & default to +5 minutes ───────────────────
  function setMinDatetime() {
    if (!dtInput) return;
    const now = new Date();
    // 5 minutes in future by default for convenience
    const plus5 = new Date(now.getTime() + 5 * 60 * 1000);
    const pad = n => String(n).padStart(2, '0');

    const minStr = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
    const defStr = `${plus5.getFullYear()}-${pad(plus5.getMonth()+1)}-${pad(plus5.getDate())}T${pad(plus5.getHours())}:${pad(plus5.getMinutes())}`;

    dtInput.min = minStr;
    if (!dtInput.value) {
      dtInput.value = defStr;
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  updateNotifBtn();
  setMinDatetime();
  updateComputerClock();
  loadReminders().then(startPolling);

  // Keep live clock running
  clockTimer = setInterval(updateComputerClock, 1000);

  // Periodically re-sync list from server every 60 seconds
  setInterval(loadReminders, 60000);

})();
