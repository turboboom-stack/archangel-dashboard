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
    animation: { duration: 400 },
    plugins: {
      legend: {
        labels: { color: '#8b96b0', boxWidth: 12, padding: 16 }
      },
      tooltip: {
        backgroundColor: '#1e2133',
        borderColor: 'rgba(255,255,255,0.12)',
        borderWidth: 1,
        titleColor: '#e4e8f0',
        bodyColor: '#8b96b0',
      }
    },
  };
}

function darkAxis(labelSuffix, position) {
  return {
    position,
    ticks: {
      color: '#8b96b0',
      callback: v => labelSuffix === '$' ? `$${v}` : v,
    },
    grid: { color: 'rgba(255,255,255,0.06)' },
    border: { color: 'rgba(255,255,255,0.08)' },
  };
}

/* Shared line dataset styling — call this to ensure lines always render */
function lineDataset(label, data, color, extra) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color + '20',  // hex color with 12% alpha
    borderWidth: 2,
    pointRadius: 5,
    pointHoverRadius: 7,
    pointBackgroundColor: color,
    tension: 0.35,
    fill: false,
    spanGaps: true,
    ...extra,
  };
}
