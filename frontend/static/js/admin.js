/**
 * admin.js — Módulo do painel de administração.
 * Gerencia aprovações, upload de templates e logs de auditoria.
 */
(function () {
  'use strict';

  let _editingTemplateId = null;
  let _editingCampos     = [];

  const Admin = {

    // -------------------------------------------------------------------------
    // Inicializa o painel: carrega stats e primeira aba
    // -------------------------------------------------------------------------
    async init() {
      await this.loadStats();
      await this.loadPendingUsers();
      setupTabs();
      setupUploadZone();
      setupModalCampos();
      setupAuditRefresh();
    },

    // -------------------------------------------------------------------------
    // Stats do dashboard
    // -------------------------------------------------------------------------
    async loadStats() {
      try {
        const s = await apiFetch('/admin/dashboard/stats');
        if (!s) return;
        document.getElementById('stat-pendentes').textContent  = s.pendentes  ?? '—';
        document.getElementById('stat-ativos').textContent     = s.ativos     ?? '—';
        document.getElementById('stat-templates').textContent  = s.templates_ativos ?? '—';
        document.getElementById('stat-hoje').textContent       = s.formularios_hoje ?? '—';
      } catch (_) {}
    },

    // -------------------------------------------------------------------------
    // Usuários pendentes
    // -------------------------------------------------------------------------
    async loadPendingUsers() {
      const container = document.getElementById('pending-users-list');
      const emptyMsg  = document.getElementById('no-pending-msg');
      try {
        const users = await apiFetch('/admin/usuarios/pendentes');
        if (!users || users.length === 0) {
          container.innerHTML = '';
          if (emptyMsg) emptyMsg.style.display = 'block';
          return;
        }
        if (emptyMsg) emptyMsg.style.display = 'none';
        container.innerHTML = '';
        users.forEach(u => container.appendChild(buildUserCard(u, true)));
      } catch (e) {
        container.innerHTML = `<p class="text-muted">${escHtml(e.message)}</p>`;
      }
    },

    // -------------------------------------------------------------------------
    // Todos os guardas
    // -------------------------------------------------------------------------
    async loadAllUsers() {
      const container = document.getElementById('all-users-list');
      try {
        const users = await apiFetch('/admin/usuarios');
        if (!users || users.length === 0) {
          container.innerHTML = '<p class="text-muted">Nenhum guarda cadastrado.</p>';
          return;
        }
        container.innerHTML = '';
        users.forEach(u => container.appendChild(buildUserCard(u, false)));
      } catch (e) {
        container.innerHTML = `<p class="text-muted">${escHtml(e.message)}</p>`;
      }
    },

    // -------------------------------------------------------------------------
    // Aprovar / Rejeitar usuário
    // -------------------------------------------------------------------------
    async aprovarUsuario(userId, acao) {
      try {
        const res = await apiFetch('/admin/usuarios/aprovar', {
          method: 'POST',
          body: JSON.stringify({ usuario_id: userId, acao }),
        });
        window.App.showToast(res.mensagem, 'success');
        await this.loadPendingUsers();
        await this.loadStats();
        await this.loadAllUsers();
      } catch (e) {
        window.App.showToast(e.message, 'error');
      }
    },

    // -------------------------------------------------------------------------
    // Upload de template
    // -------------------------------------------------------------------------
    async uploadTemplate(nome, descricao, file) {
      const formData = new FormData();
      formData.append('nome_documento', nome.toUpperCase());
      if (descricao) formData.append('descricao', descricao);
      formData.append('arquivo', file);

      const token = Auth.getToken();
      const res   = await fetch('/api/admin/templates', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erro no upload.');
      return data;
    },

    // -------------------------------------------------------------------------
    // Lista de templates (admin)
    // -------------------------------------------------------------------------
    async loadTemplates() {
      const container = document.getElementById('admin-templates-list');
      try {
        const templates = await apiFetch('/admin/templates');
        if (!templates || templates.length === 0) {
          container.innerHTML = '<p class="text-muted">Nenhum template cadastrado.</p>';
          return;
        }
        container.innerHTML = '';
        templates.forEach(t => container.appendChild(buildTemplateCard(t)));
      } catch (e) {
        container.innerHTML = `<p class="text-muted">${escHtml(e.message)}</p>`;
      }
    },

    // -------------------------------------------------------------------------
    // Desativar template
    // -------------------------------------------------------------------------
    async desativarTemplate(id) {
      if (!confirm('Desativar este template? Os guardas não poderão mais acessá-lo.')) return;
      try {
        await apiFetch(`/admin/templates/${id}`, { method: 'DELETE' });
        window.App.showToast('Template desativado.', 'success');
        await this.loadTemplates();
      } catch (e) {
        window.App.showToast(e.message, 'error');
      }
    },

    // -------------------------------------------------------------------------
    // Abrir editor de campos
    // -------------------------------------------------------------------------
    openCamposEditor(template) {
      _editingTemplateId = template.id;
      _editingCampos     = [...(template.campos || [])];
      document.getElementById('modal-campos-title').textContent =
        `Campos: ${template.nome_documento}`;
      renderCamposEditor();
      document.getElementById('modal-campos').style.display = 'block';
    },

    // -------------------------------------------------------------------------
    // Salvar campos do template
    // -------------------------------------------------------------------------
    async saveCampos() {
      const editor = document.getElementById('campos-editor-list');
      const items  = editor.querySelectorAll('.campo-editor-item');
      const campos = [];
      items.forEach((item, idx) => {
        const label     = item.querySelector('.campo-label-input').value.trim();
        const tipo      = item.querySelector('.campo-tipo-select').value;
        const obrig     = item.querySelector('.campo-obrig-check').checked;
        const opcoes    = item.querySelector('.campo-opcoes-input')?.value.trim() || null;
        if (!label) return;
        campos.push({
          nome_campo:  slugify(label),
          label,
          tipo_campo:  tipo,
          obrigatorio: obrig,
          opcoes:      opcoes ? JSON.stringify(opcoes.split('\n').map(s => s.trim()).filter(Boolean)) : null,
          ordem:       idx,
          coordenadas_pdf: null,
        });
      });

      try {
        await apiFetch(`/admin/templates/${_editingTemplateId}/campos`, {
          method: 'POST',
          body: JSON.stringify(campos),
        });
        window.App.showToast('Campos salvos com sucesso!', 'success');
        document.getElementById('modal-campos').style.display = 'none';
        await this.loadTemplates();
      } catch (e) {
        window.App.showToast(e.message, 'error');
      }
    },

    // -------------------------------------------------------------------------
    // Logs de auditoria
    // -------------------------------------------------------------------------
    async loadAuditLogs() {
      const container = document.getElementById('audit-log-list');
      try {
        const logs = await apiFetch('/admin/auditoria?limite=100');
        if (!logs || logs.length === 0) {
          container.innerHTML = '<p class="text-muted">Nenhum log registrado.</p>';
          return;
        }
        container.innerHTML = '';
        logs.forEach(l => {
          const item = document.createElement('div');
          item.className = 'log-item';
          const dt = new Date(l.timestamp).toLocaleString('pt-BR');
          item.innerHTML = `
            <div>
              <span class="log-acao">${escHtml(l.acao)}</span>
              <div class="log-time">${escHtml(dt)}</div>
            </div>
            <div class="log-body">
              <div class="log-usuario">${escHtml(l.nome_usuario || 'Sistema')} (${escHtml(l.matricula_usuario || '—')})</div>
              <div class="log-detalhe">${escHtml(l.detalhes || '')} ${l.ip_origem ? `· IP: ${escHtml(l.ip_origem)}` : ''}</div>
            </div>`;
          container.appendChild(item);
        });
      } catch (e) {
        container.innerHTML = `<p class="text-muted">${escHtml(e.message)}</p>`;
      }
    },
  };

  // ---------------------------------------------------------------------------
  // Construtores de HTML
  // ---------------------------------------------------------------------------

  function buildUserCard(u, showApproveButtons) {
    const card = document.createElement('div');
    card.className = 'user-card';
    const initials = (u.nome || 'GM').split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase();
    const badgeClass = {
      pendente: 'badge-pending', ativo: 'badge-active',
      inativo: 'badge-inactive', rejeitado: 'badge-rejected',
    }[u.status_aprovacao] || 'badge-inactive';
    const badgeLabel = { pendente: 'Pendente', ativo: 'Ativo', inativo: 'Inativo', rejeitado: 'Rejeitado' }[u.status_aprovacao] || u.status_aprovacao;

    const btns = showApproveButtons
      ? `<button class="btn btn-success" style="padding:8px 14px;font-size:13px;" onclick="Admin.aprovarUsuario(${u.id},'aprovar')">✓ Aprovar</button>
         <button class="btn btn-danger"  style="padding:8px 14px;font-size:13px;" onclick="Admin.aprovarUsuario(${u.id},'rejeitar')">✕ Rejeitar</button>`
      : `<button class="btn btn-ghost"   style="padding:8px 14px;font-size:13px;" onclick="Admin.aprovarUsuario(${u.id},'inativar')">🚫 Inativar</button>`;

    card.innerHTML = `
      <div class="user-avatar">${escHtml(initials)}</div>
      <div class="user-info">
        <div class="user-name">${escHtml(u.nome)}</div>
        <div class="user-meta">Mat.: ${escHtml(u.matricula)} · ${escHtml(u.equipe || '—')}</div>
        <div style="margin-top:4px;"><span class="badge ${badgeClass}">${badgeLabel}</span></div>
      </div>
      <div class="user-actions">${btns}</div>`;
    return card;
  }

  function buildTemplateCard(t) {
    const card = document.createElement('div');
    card.className = 'card mb-2';
    const dt = new Date(t.data_upload).toLocaleDateString('pt-BR');
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div style="flex:1;min-width:0;">
          <div style="font-weight:700;font-size:15px;">${escHtml(t.nome_documento)}</div>
          <div style="font-size:12px;color:var(--text-muted);">${escHtml(t.descricao || '—')} · ${t.campos.length} campo(s) · ${dt}</div>
          <div style="margin-top:4px;"><span class="badge ${t.status === 'ativo' ? 'badge-active' : 'badge-inactive'}">${t.status}</span></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <button class="btn btn-ghost" style="padding:7px 12px;font-size:12px;"
                  onclick="Admin.openCamposEditor(${escAttr(JSON.stringify(t))})">
            ✏️ Campos
          </button>
          <button class="btn btn-danger" style="padding:7px 12px;font-size:12px;"
                  onclick="Admin.desativarTemplate(${t.id})">
            🗑 Remover
          </button>
        </div>
      </div>`;
    return card;
  }

  // ---------------------------------------------------------------------------
  // Editor de campos
  // ---------------------------------------------------------------------------

  function renderCamposEditor() {
    const container = document.getElementById('campos-editor-list');
    container.innerHTML = '';
    _editingCampos.forEach((c, i) => addCampoEditorItem(container, c, i));
  }

  function addCampoEditorItem(container, c = {}, idx = 0) {
    const div = document.createElement('div');
    div.className = 'campo-editor-item';
    div.innerHTML = `
      <button class="campo-remove-btn" type="button" title="Remover campo">✕</button>
      <div class="campo-editor-grid">
        <div class="form-group mb-0">
          <label class="form-label" style="font-size:11px;">Rótulo (Label)</label>
          <input class="form-control campo-label-input" type="text" style="min-height:40px;"
                 value="${escHtml(c.label || '')}" placeholder="Ex: Nome do Abordado">
        </div>
        <div class="form-group mb-0">
          <label class="form-label" style="font-size:11px;">Tipo</label>
          <select class="form-control campo-tipo-select" style="min-height:40px;">
            ${['text','number','date','time','textarea','select','checkbox','cpf','placa']
              .map(t => `<option value="${t}" ${c.tipo_campo === t ? 'selected' : ''}>${t}</option>`)
              .join('')}
          </select>
        </div>
      </div>
      <div class="form-group mt-1 mb-0" style="display:flex;align-items:center;gap:8px;">
        <input type="checkbox" class="form-check-input campo-obrig-check" id="obrig-${idx}"
               ${c.obrigatorio !== false ? 'checked' : ''}>
        <label style="font-size:13px;cursor:pointer;" for="obrig-${idx}">Obrigatório</label>
      </div>
      <div class="campo-opcoes-wrapper form-group mb-0 mt-1" style="display:${c.tipo_campo==='select'?'block':'none'}">
        <label class="form-label" style="font-size:11px;">Opções (uma por linha)</label>
        <textarea class="form-control campo-opcoes-input" rows="3" style="min-height:unset;text-transform:none;"
                  placeholder="Opção 1&#10;Opção 2&#10;Opção 3">${c.opcoes ? (Array.isArray(c.opcoes) ? c.opcoes.join('\n') : tryParseOpcoes(c.opcoes)) : ''}</textarea>
      </div>`;

    // Mostra/oculta campo de opções conforme tipo
    div.querySelector('.campo-tipo-select').addEventListener('change', function () {
      div.querySelector('.campo-opcoes-wrapper').style.display =
        this.value === 'select' ? 'block' : 'none';
    });

    div.querySelector('.campo-remove-btn').addEventListener('click', () => {
      div.remove();
    });

    container.appendChild(div);
  }

  function tryParseOpcoes(raw) {
    try { return JSON.parse(raw).join('\n'); } catch { return raw; }
  }

  // ---------------------------------------------------------------------------
  // Setup de eventos
  // ---------------------------------------------------------------------------

  function setupTabs() {
    const tabBtns = document.querySelectorAll('.admin-tab');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', async () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.admin-tab-panel').forEach(p => p.classList.remove('active'));
        const panelId = `tab-${btn.dataset.tab}`;
        const panel   = document.getElementById(panelId);
        if (panel) panel.classList.add('active');

        // Lazy-load ao trocar de aba
        if (btn.dataset.tab === 'templates') await Admin.loadTemplates();
        if (btn.dataset.tab === 'auditoria')  await Admin.loadAuditLogs();
        if (btn.dataset.tab === 'guardas')    await Admin.loadAllUsers();
      });
    });
  }

  function setupUploadZone() {
    const zone  = document.getElementById('upload-zone');
    const input = document.getElementById('tpl-file');
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) {
        input.files = e.dataTransfer.files;
        updateUploadHint(e.dataTransfer.files[0].name);
      }
    });
    input.addEventListener('change', () => {
      if (input.files[0]) updateUploadHint(input.files[0].name);
    });

    const form = document.getElementById('form-upload-template');
    if (form) {
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const nome   = document.getElementById('tpl-nome').value.trim();
        const descr  = document.getElementById('tpl-desc').value.trim();
        const file   = input.files[0];
        if (!nome || !file) { window.App.showToast('Preencha o nome e selecione o PDF.', 'warning'); return; }

        const btn = document.getElementById('btn-upload-template');
        btn.textContent = 'Enviando...';
        btn.disabled = true;
        try {
          await Admin.uploadTemplate(nome, descr, file);
          window.App.showToast('Template enviado com sucesso!', 'success');
          form.reset();
          updateUploadHint('PDF nativo ou escaneado · Máx. 20 MB');
          await Admin.loadTemplates();
          await Admin.loadStats();
        } catch (err) {
          window.App.showToast(err.message, 'error');
        } finally {
          btn.textContent = '⬆ Enviar Template';
          btn.disabled = false;
        }
      });
    }
  }

  function updateUploadHint(texto) {
    const hint = document.getElementById('upload-hint');
    if (hint) hint.textContent = `📎 ${texto}`;
  }

  function setupModalCampos() {
    document.getElementById('btn-add-campo')?.addEventListener('click', () => {
      addCampoEditorItem(document.getElementById('campos-editor-list'));
    });
    document.getElementById('btn-close-modal')?.addEventListener('click', () => {
      document.getElementById('modal-campos').style.display = 'none';
    });
    document.getElementById('btn-cancel-campos')?.addEventListener('click', () => {
      document.getElementById('modal-campos').style.display = 'none';
    });
    document.getElementById('btn-save-campos')?.addEventListener('click', () => Admin.saveCampos());
  }

  function setupAuditRefresh() {
    document.getElementById('btn-refresh-audit')?.addEventListener('click', () => Admin.loadAuditLogs());
  }

  // ---------------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------------

  function slugify(text) {
    return text.toLowerCase().trim()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, '_').slice(0, 50);
  }

  function escAttr(s) {
    return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  window.Admin = Admin;

})();
