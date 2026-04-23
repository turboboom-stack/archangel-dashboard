/* Archangel Command Center — shared JS */

function showToast(msg, isError = false) {
  const toast = document.getElementById('mainToast');
  const body = document.getElementById('toastBody');
  if (!toast || !body) return;
  body.textContent = msg;
  toast.classList.toggle('text-bg-danger', isError);
  toast.classList.toggle('text-bg-dark', !isError);
  new bootstrap.Toast(toast, { delay: 4000 }).show();
}

function refreshAll(btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Refreshing…'; }
  fetch('/api/refresh/all', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      showToast('Refreshing data — reloading in 8 seconds…');
      setTimeout(() => location.reload(), 8000);
    })
    .catch(() => {
      showToast('Refresh failed', true);
      if (btn) { btn.disabled = false; btn.textContent = 'Refresh All'; }
    });
}

function refreshSource(source) {
  fetch(`/api/refresh/${source}`, { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      showToast(`${source} refreshed`);
      setTimeout(() => location.reload(), 1500);
    })
    .catch(() => showToast(`Failed to refresh ${source}`, true));
}

function dismissItem(id) {
  fetch(`/api/action-items/dismiss/${id}`, { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      const el = document.getElementById(`ai-${id}`);
      if (el) { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }
    });
}

function refreshActionItems() {
  fetch('/api/action-items/refresh', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      showToast(`Action items refreshed: ${d.count} found`);
      setTimeout(() => location.reload(), 1500);
    });
}

/* Chart.js shared dark theme helpers */
function darkChartOptions() {
  return {
    responsive: true,
    plugins: {
      legend: {
        labels: { color: '#aaa', boxWidth: 12 }
      }
    },
  };
}

function darkAxis(labelSuffix, position) {
  return {
    position,
    ticks: { color: '#aaa', callback: v => `${v}${labelSuffix === '$' ? '' : ''}` },
    grid: { color: 'rgba(255,255,255,0.07)' },
  };
}
