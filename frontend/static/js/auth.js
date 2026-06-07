/**
 * auth.js — Módulo de autenticação.
 * Gerencia login, registro, armazenamento do token JWT e status do usuário.
 */
(function () {
  'use strict';

  const TOKEN_KEY = 'gm_token';
  const USER_KEY  = 'gm_user';
  const API_BASE  = '/api';

  // ---------------------------------------------------------------------------
  // Helpers HTTP
  // ---------------------------------------------------------------------------

  async function apiFetch(path, options = {}) {
    const token = Auth.getToken();
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const resp = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (resp.status === 401) {
      Auth.logout();
      return null;
    }

    const contentType = resp.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await resp.json() : null;

    if (!resp.ok) {
      const detail = data?.detail || `Erro ${resp.status}`;
      throw new Error(detail);
    }

    return data;
  }

  // ---------------------------------------------------------------------------
  // API pública do módulo
  // ---------------------------------------------------------------------------

  const Auth = {
    getToken() {
      return localStorage.getItem(TOKEN_KEY);
    },

    getUser() {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    },

    isAuthenticated() {
      return !!this.getToken();
    },

    isAdmin() {
      const user = this.getUser();
      return user && user.is_admin === true;
    },

    saveSession(token, usuario) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(usuario));
    },

    logout() {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      window.App && window.App.navigate('login');
    },

    async login(matricula, senha) {
      const data = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ matricula: matricula.trim().toUpperCase(), senha }),
      });
      if (!data) throw new Error('Erro ao processar login.');
      this.saveSession(data.access_token, data.usuario);
      return data.usuario;
    },

    async register(nome, matricula, equipe, senha) {
      const data = await apiFetch('/auth/registrar', {
        method: 'POST',
        body: JSON.stringify({
          nome:      nome.trim(),
          matricula: matricula.trim().toUpperCase(),
          equipe:    equipe.trim() || null,
          senha,
        }),
      });
      return data;
    },

    async checkStatus() {
      const data = await apiFetch('/auth/status');
      if (!data) return null;
      // Atualiza o usuário em cache
      const user = this.getUser();
      if (user) {
        user.status_aprovacao = data.status_aprovacao;
        localStorage.setItem(USER_KEY, JSON.stringify(user));
      }
      return data;
    },
  };

  // Expõe globalmente
  window.Auth     = Auth;
  window.apiFetch = apiFetch;

})();
