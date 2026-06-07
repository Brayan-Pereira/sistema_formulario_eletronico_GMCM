/**
 * app.js — Orquestrador principal do SPA.
 * Gerencia navegação entre views, eventos globais e estado da aplicação.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Estado
  // ---------------------------------------------------------------------------
  let _currentView = null;
  let _statusPollInterval = null;

  // ---------------------------------------------------------------------------
  // Utilitários de UI
  // ---------------------------------------------------------------------------

  function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const view = document.getElementById(`view-${viewId}`);
    if (view) {
      view.classList.add('active');
      _currentView = viewId;
      window.scrollTo(0, 0);
    }
  }

  function showHeader(visible, title = 'Guarda Municipal') {
    const header = document.getElementById('app-header');
    const content = document.getElementById('main-content');
    if (visible) {
      header.classList.remove('d-none');
      content.style.paddingTop = '0';
    } else {
      header.classList.add('d-none');
      content.style.paddingTop = '0';
    }
    document.getElementById('header-title').textContent = title;
  }

  function showAdminButton(visible) {
    document.getElementById('btn-admin-panel').classList.toggle('d-none', !visible);
  }

  function showLoading(visible) {
    let overlay = document.getElementById('loading-overlay');
    if (visible && !overlay) {
      overlay = document.createElement('div');
      overlay.id = 'loading-overlay';
      overlay.className = 'loading-overlay';
      overlay.innerHTML = '<div class="loading-spinner"></div>';
      document.body.appendChild(overlay);
    } else if (!visible && overlay) {
      overlay.remove();
    }
  }

  // ---------------------------------------------------------------------------
  // Sistema de Toasts
  // ---------------------------------------------------------------------------

  function showToast(msg, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity .3s';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ---------------------------------------------------------------------------
  // Navegação
  // ---------------------------------------------------------------------------

  const App = {
    navigate(route, ...args) {
      stopStatusPoll();

      switch (route) {
        case 'login':    showLoginView();    break;
        case 'register': showRegisterView(); break;
        case 'pending':  showPendingView();  break;
        case 'dashboard':showDashboardView();break;
        case 'admin':    showAdminView();    break;
        default:
          console.warn('Rota desconhecida:', route);
      }
    },

    openForm(templateId) {
      const tpl = Forms.getTemplateById(templateId) ||
                  Forms.loadTemplates().then(tpls => tpls.find(t => t.template_id === templateId));
      if (!tpl) {
        showToast('Formulário não encontrado.', 'error');
        return;
      }
      Forms.renderForm(tpl);
      showHeader(true, tpl.nome_documento);
      showView('form');
    },

    showQRCode(info) {
      document.getElementById('qr-doc-title').textContent     = info.nome_documento || 'Documento';
      document.getElementById('qr-info-doc').textContent      = info.nome_documento || '—';
      document.getElementById('qr-info-guarda').textContent   = info.nome_guarda_autoria || '—';
      document.getElementById('qr-info-matricula').textContent = info.matricula_guarda_autoria || '—';
      const dt = info.data_criacao ? new Date(info.data_criacao).toLocaleString('pt-BR') : '—';
      document.getElementById('qr-info-data').textContent     = dt;
      document.getElementById('qr-url-text').textContent      = info.url_download || '—';

      const qrImg = document.getElementById('qr-image');
      if (info.url_qrcode) {
        qrImg.src = info.url_qrcode + '?t=' + Date.now();
        qrImg.onerror = () => {
          qrImg.alt = '(QR Code indisponível — use o link acima)';
          qrImg.style.display = 'none';
        };
      }

      const downloadBtn = document.getElementById('qr-btn-download');
      downloadBtn.href = info.url_download || '#';

      showHeader(true, 'Documento Emitido');
      showAdminButton(Auth.isAdmin());
      showView('qrcode');
    },

    showToast,
  };

  // ---------------------------------------------------------------------------
  // Views
  // ---------------------------------------------------------------------------

  function showLoginView() {
    showHeader(false);
    showView('login');
    // Não mostra main-content com padding extra
    document.getElementById('main-content').style.padding = '0';
  }

  function showRegisterView() {
    showHeader(false);
    showView('register');
    document.getElementById('main-content').style.padding = '0';
  }

  function showPendingView() {
    const user = Auth.getUser();
    showHeader(false);
    if (user) {
      document.getElementById('pending-user-info').textContent =
        `${user.nome} — Mat.: ${user.matricula} ${user.equipe ? '· ' + user.equipe : ''}`;
    }
    showView('pending');
    document.getElementById('main-content').style.padding = '0';
    startStatusPoll();
  }

  async function showDashboardView() {
    const user = Auth.getUser();
    showHeader(true, 'Guarda Municipal');
    showAdminButton(Auth.isAdmin());
    document.getElementById('main-content').style.padding = '20px 16px 80px';

    if (user) {
      const hora = new Date().getHours();
      const saud = hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite';
      document.getElementById('dashboard-greeting').textContent =
        `${saud}, ${user.nome.split(' ')[0]}!`;
      document.getElementById('dashboard-user-info').textContent =
        `Mat.: ${user.matricula}${user.equipe ? ' · ' + user.equipe : ''}`;
    }

    // Carrega templates
    const listEl   = document.getElementById('template-list');
    const loadingEl = document.getElementById('templates-loading');
    if (loadingEl) loadingEl.style.display = 'block';
    try {
      const templates = await Forms.loadTemplates();
      if (loadingEl) loadingEl.style.display = 'none';
      Forms.renderTemplateList(templates, listEl);
    } catch (e) {
      if (loadingEl) loadingEl.textContent = 'Erro ao carregar formulários.';
    }

    // Carrega histórico
    const recentList = document.getElementById('recent-list');
    const recentEmpty = document.getElementById('recent-empty');
    await Forms.loadRecentForms(recentList, recentEmpty);

    showView('dashboard');
  }

  async function showAdminView() {
    if (!Auth.isAdmin()) { showToast('Acesso restrito.', 'error'); return; }
    showHeader(true, 'Painel Admin');
    showAdminButton(true);
    document.getElementById('main-content').style.padding = '20px 16px 80px';
    showView('admin');
    await Admin.init();
  }

  // ---------------------------------------------------------------------------
  // Polling de status (tela de espera)
  // ---------------------------------------------------------------------------

  function startStatusPoll() {
    if (_statusPollInterval) return;
    _statusPollInterval = setInterval(async () => {
      try {
        const status = await Auth.checkStatus();
        if (status && status.status_aprovacao === 'ativo') {
          stopStatusPoll();
          showToast('Seu acesso foi aprovado! Bem-vindo.', 'success');
          App.navigate('dashboard');
        } else if (status && status.status_aprovacao === 'rejeitado') {
          stopStatusPoll();
          showToast('Seu cadastro foi rejeitado. Entre em contato com a chefia.', 'error');
          Auth.logout();
        }
      } catch (_) {}
    }, 15000); // Verifica a cada 15 segundos
  }

  function stopStatusPoll() {
    if (_statusPollInterval) {
      clearInterval(_statusPollInterval);
      _statusPollInterval = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Dark Mode
  // ---------------------------------------------------------------------------

  function initDarkMode() {
    const html   = document.documentElement;
    const btn    = document.getElementById('btn-dark-mode');
    const stored = localStorage.getItem('gm_theme');

    // Detecta preferência do sistema
    const prefDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme    = stored || (prefDark ? 'dark' : 'light');
    html.setAttribute('data-theme', theme);
    btn && (btn.textContent = theme === 'dark' ? '☀️' : '🌙');

    btn && btn.addEventListener('click', () => {
      const current = html.getAttribute('data-theme');
      const next    = current === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('gm_theme', next);
      btn.textContent = next === 'dark' ? '☀️' : '🌙';
    });
  }

  // ---------------------------------------------------------------------------
  // Bindings de eventos
  // ---------------------------------------------------------------------------

  function bindEvents() {
    // --- Login ---
    document.getElementById('form-login')?.addEventListener('submit', async e => {
      e.preventDefault();
      const mat   = document.getElementById('login-matricula').value.trim();
      const senha = document.getElementById('login-senha').value;
      if (!mat || !senha) { showToast('Preencha todos os campos.', 'warning'); return; }

      const btn = document.getElementById('btn-login');
      setButtonLoading(btn, true);
      try {
        const user = await Auth.login(mat, senha);
        if (user.status_aprovacao === 'ativo') {
          App.navigate('dashboard');
        } else if (user.status_aprovacao === 'pendente') {
          App.navigate('pending');
        }
      } catch (e) {
        showToast(e.message, 'error');
      } finally {
        setButtonLoading(btn, false);
      }
    });

    document.getElementById('link-to-register')?.addEventListener('click', e => {
      e.preventDefault();
      App.navigate('register');
    });

    // --- Registro ---
    document.getElementById('form-register')?.addEventListener('submit', async e => {
      e.preventDefault();
      const nome   = document.getElementById('reg-nome').value.trim();
      const mat    = document.getElementById('reg-matricula').value.trim();
      const equipe = document.getElementById('reg-equipe').value.trim();
      const senha  = document.getElementById('reg-senha').value;
      const senha2 = document.getElementById('reg-senha2').value;

      if (!nome || !mat || !senha) { showToast('Preencha todos os campos obrigatórios.', 'warning'); return; }
      if (senha !== senha2) { showToast('As senhas não coincidem.', 'error'); return; }
      if (senha.length < 6) { showToast('Senha deve ter no mínimo 6 caracteres.', 'error'); return; }

      const btn = document.getElementById('btn-register');
      setButtonLoading(btn, true);
      try {
        await Auth.register(nome, mat, equipe, senha);
        showToast('Cadastro enviado! Aguarde aprovação.', 'success');
        // Faz login automático para exibir tela de espera
        try {
          await Auth.login(mat, senha);
        } catch (_) {}
        App.navigate('pending');
      } catch (e) {
        showToast(e.message, 'error');
      } finally {
        setButtonLoading(btn, false);
      }
    });

    document.getElementById('link-to-login')?.addEventListener('click', e => {
      e.preventDefault();
      App.navigate('login');
    });

    // --- Tela de espera ---
    document.getElementById('btn-check-status')?.addEventListener('click', async () => {
      try {
        const status = await Auth.checkStatus();
        if (!status) return;
        if (status.status_aprovacao === 'ativo') {
          showToast('Acesso aprovado!', 'success');
          App.navigate('dashboard');
        } else if (status.status_aprovacao === 'rejeitado') {
          showToast('Cadastro rejeitado.', 'error');
          Auth.logout();
        } else {
          showToast('Ainda aguardando aprovação...', 'info');
        }
      } catch (e) { showToast(e.message, 'error'); }
    });

    document.getElementById('btn-logout-pending')?.addEventListener('click', () => Auth.logout());

    // --- Formulário dinâmico ---
    document.getElementById('form-dynamic')?.addEventListener('submit', async e => {
      e.preventDefault();
      const tpl   = Forms.getCurrentTemplate();
      if (!tpl) return;
      const dados = Forms.collectFormData();
      if (!dados) { showToast('Preencha todos os campos obrigatórios.', 'warning'); return; }

      const btn = document.getElementById('btn-form-submit');
      setButtonLoading(btn, true);
      showLoading(true);
      try {
        const resposta = await Forms.submitForm(tpl.template_id, dados);
        showLoading(false);
        App.showQRCode({
          nome_documento: tpl.nome_documento,
          token_hash_unico: resposta.token_hash_unico,
          nome_guarda_autoria: resposta.nome_guarda_autoria,
          matricula_guarda_autoria: resposta.matricula_guarda_autoria,
          data_criacao: resposta.data_criacao,
          url_qrcode: resposta.url_qrcode,
          url_download: resposta.url_download,
        });
        showToast('Documento emitido com sucesso!', 'success');
      } catch (e) {
        showLoading(false);
        showToast(e.message, 'error');
      } finally {
        setButtonLoading(btn, false);
      }
    });

    document.getElementById('btn-form-back')?.addEventListener('click', () => App.navigate('dashboard'));

    // --- QR Code ---
    document.getElementById('btn-novo-formulario')?.addEventListener('click', () => App.navigate('dashboard'));

    // --- Header ---
    document.getElementById('btn-logout')?.addEventListener('click', () => {
      if (confirm('Deseja sair do sistema?')) Auth.logout();
    });

    document.getElementById('btn-admin-panel')?.addEventListener('click', () => {
      if (_currentView === 'admin') App.navigate('dashboard');
      else App.navigate('admin');
    });
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.setAttribute('aria-busy', loading ? 'true' : 'false');
    if (loading) btn.classList.add('btn-loading');
    else         btn.classList.remove('btn-loading');
  }

  // ---------------------------------------------------------------------------
  // Inicialização
  // ---------------------------------------------------------------------------

  function init() {
    initDarkMode();
    bindEvents();

    // Roteamento inicial
    if (!Auth.isAuthenticated()) {
      App.navigate('login');
      return;
    }

    const user = Auth.getUser();
    if (!user) { Auth.logout(); return; }

    if (user.status_aprovacao === 'ativo') {
      if (user.is_admin) App.navigate('admin');
      else App.navigate('dashboard');
    } else if (user.status_aprovacao === 'pendente') {
      App.navigate('pending');
    } else {
      Auth.logout();
    }
  }

  window.App = App;
  document.addEventListener('DOMContentLoaded', init);

})();
