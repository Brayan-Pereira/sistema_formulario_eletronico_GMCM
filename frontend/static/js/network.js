/**
 * network.js — Monitoramento de conectividade e retry inteligente.
 * Exibe banner quando o dispositivo perde a conexão de internet.
 */
(function () {
  'use strict';

  const banner   = document.getElementById('network-banner');
  const msgEl    = document.getElementById('network-msg');
  let isOffline  = false;
  let retryTimer = null;

  function setOffline() {
    if (isOffline) return;
    isOffline = true;
    banner.classList.add('offline');
    msgEl.textContent = '⚠ Sem conexão — Tentando reconectar...';
    scheduleRetry();
  }

  function setOnline() {
    isOffline = false;
    banner.classList.remove('offline');
    if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
  }

  function scheduleRetry() {
    if (retryTimer) return;
    retryTimer = setTimeout(async () => {
      retryTimer = null;
      try {
        const res = await fetch('/api/auth/me', {
          method: 'HEAD',
          cache: 'no-store',
          signal: AbortSignal.timeout(5000),
        });
        if (res.status < 500) setOnline();
        else scheduleRetry();
      } catch {
        scheduleRetry();
      }
    }, 5000);
  }

  window.addEventListener('online',  setOnline);
  window.addEventListener('offline', setOffline);

  if (!navigator.onLine) setOffline();

  // Expõe para outros módulos usarem
  window.Network = { isOffline: () => isOffline };
})();
