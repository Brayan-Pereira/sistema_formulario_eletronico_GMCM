/**
 * forms.js — Renderização dinâmica de formulários e envio para o backend.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Cache de templates
  // ---------------------------------------------------------------------------
  let _templates = [];
  let _currentTemplate = null;

  const Forms = {

    // -------------------------------------------------------------------------
    // Carrega a lista de templates disponíveis
    // -------------------------------------------------------------------------
    async loadTemplates() {
      const data = await apiFetch('/forms/templates');
      if (!data) return [];
      _templates = data;
      return data;
    },

    getTemplateById(id) {
      return _templates.find(t => t.template_id === id || t.template_id === Number(id));
    },

    // -------------------------------------------------------------------------
    // Renderiza a lista de templates no dashboard
    // -------------------------------------------------------------------------
    renderTemplateList(templates, container) {
      container.innerHTML = '';

      if (!templates || templates.length === 0) {
        container.innerHTML = `
          <div style="text-align:center;padding:40px 20px;color:var(--text-muted);">
            <div style="font-size:48px;margin-bottom:12px;">📋</div>
            <p>Nenhum formulário disponível.<br>Aguarde o Administrador cadastrar modelos.</p>
          </div>`;
        return;
      }

      const icons = ['📋', '📝', '🗒️', '📃', '📑', '🗃️', '📄', '✍️'];
      templates.forEach((tpl, idx) => {
        const card = document.createElement('div');
        card.className = 'template-card';
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.dataset.templateId = tpl.template_id;
        card.innerHTML = `
          <div class="template-icon">${icons[idx % icons.length]}</div>
          <div class="template-info">
            <div class="template-name">${escHtml(tpl.nome_documento)}</div>
            <div class="template-desc">${escHtml(tpl.descricao || `${tpl.campos.length} campo(s)`)}</div>
          </div>
          <div class="template-arrow">›</div>`;
        card.addEventListener('click', () => window.App.openForm(tpl.template_id));
        card.addEventListener('keypress', e => e.key === 'Enter' && window.App.openForm(tpl.template_id));
        container.appendChild(card);
      });
    },

    // -------------------------------------------------------------------------
    // Renderiza formulário dinâmico a partir do contrato JSON
    // -------------------------------------------------------------------------
    renderForm(template) {
      _currentTemplate = template;

      document.getElementById('form-dynamic-title').textContent = template.nome_documento;
      document.getElementById('form-dynamic-subtitle').textContent =
        template.descricao || `${template.campos.length} campo(s) obrigatório(s)`;

      const container = document.getElementById('form-fields-container');
      container.innerHTML = '';

      const campos = [...template.campos].sort((a, b) => a.ordem - b.ordem);

      campos.forEach(campo => {
        const group = document.createElement('div');
        group.className = 'field-section';
        group.innerHTML = `
          <div class="form-group mb-0">
            <label class="form-label" for="field-${campo.id}">
              ${escHtml(campo.label)}
              ${campo.obrigatorio ? '<span class="required">*</span>' : ''}
            </label>
            ${buildFieldInput(campo)}
            <span class="form-error">Campo obrigatório.</span>
          </div>`;
        container.appendChild(group);
      });

      updateProgress();
    },

    // -------------------------------------------------------------------------
    // Coleta e valida os dados do formulário
    // -------------------------------------------------------------------------
    collectFormData() {
      if (!_currentTemplate) return null;

      const dados = {};
      let valido = true;

      const campos = [..._currentTemplate.campos].sort((a, b) => a.ordem - b.ordem);

      campos.forEach(campo => {
        const el = document.getElementById(`field-${campo.id}`);
        if (!el) return;

        let valor = '';
        if (campo.tipo_campo === 'checkbox') {
          valor = el.checked ? 'SIM' : 'NÃO';
        } else {
          valor = el.value.trim();
        }

        if (campo.obrigatorio && !valor && campo.tipo_campo !== 'checkbox') {
          el.classList.add('error');
          valido = false;
        } else {
          el.classList.remove('error');
        }

        dados[campo.nome_campo] = valor;
      });

      return valido ? dados : null;
    },

    // -------------------------------------------------------------------------
    // Envia formulário ao backend
    // -------------------------------------------------------------------------
    async submitForm(templateId, dados) {
      const resposta = await apiFetch('/forms/submeter', {
        method: 'POST',
        body: JSON.stringify({ template_id: templateId, dados }),
      });
      return resposta;
    },

    // -------------------------------------------------------------------------
    // Renderiza o histórico de formulários recentes
    // -------------------------------------------------------------------------
    async loadRecentForms(container, emptyEl) {
      try {
        const data = await apiFetch('/forms/meus-formularios');
        if (!data || data.length === 0) {
          if (emptyEl) emptyEl.style.display = 'block';
          return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        container.innerHTML = '';
        data.slice(0, 5).forEach(f => {
          const tpl = _templates.find(t => t.template_id === f.template_id);
          const nome = tpl ? tpl.nome_documento : `Formulário #${f.template_id}`;
          const dt   = new Date(f.data_criacao).toLocaleString('pt-BR');
          const item = document.createElement('div');
          item.className = 'card';
          item.style.cssText = 'padding:14px;cursor:pointer;';
          item.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <div>
                <div style="font-weight:700;font-size:14px;">${escHtml(nome)}</div>
                <div style="font-size:12px;color:var(--text-muted);">${dt}</div>
              </div>
              <span style="font-size:18px;color:var(--success);">✓</span>
            </div>`;
          item.addEventListener('click', () => {
            window.App.showQRCode({
              token_hash_unico: f.token_hash_unico,
              nome_documento: nome,
              nome_guarda_autoria: f.nome_guarda_autoria,
              matricula_guarda_autoria: f.matricula_guarda_autoria,
              data_criacao: f.data_criacao,
              url_qrcode: f.url_qrcode,
              url_download: f.url_download,
            });
          });
          container.appendChild(item);
        });
      } catch (e) {
        // Silencia erro no carregamento do histórico
      }
    },

    getCurrentTemplate() { return _currentTemplate; },
  };

  // ---------------------------------------------------------------------------
  // Builders de campos HTML
  // ---------------------------------------------------------------------------

  function buildFieldInput(campo) {
    const id = `field-${campo.id}`;
    const req = campo.obrigatorio ? 'required' : '';

    switch (campo.tipo_campo) {
      case 'date':
        return `<input class="form-control" type="date" id="${id}" ${req}
                       style="text-transform:none;">`;

      case 'time':
        return `<input class="form-control" type="time" id="${id}" ${req}
                       style="text-transform:none;">`;

      case 'number':
        return `<input class="form-control" type="tel" id="${id}"
                       inputmode="numeric" pattern="[0-9\\-\\./]*"
                       placeholder="Apenas números" ${req}>`;

      case 'cpf':
        return `<input class="form-control" type="tel" id="${id}"
                       inputmode="numeric" maxlength="14"
                       placeholder="000.000.000-00"
                       oninput="maskCPF(this)" ${req}>`;

      case 'placa':
        return `<input class="form-control" type="text" id="${id}"
                       maxlength="8" placeholder="ABC-1234 ou ABC1D23"
                       autocapitalize="characters"
                       oninput="this.value=this.value.toUpperCase()" ${req}>`;

      case 'textarea':
        return `<textarea class="form-control" id="${id}" rows="4"
                          style="text-transform:none;" ${req}
                          placeholder="Descreva detalhadamente..."></textarea>`;

      case 'select':
        const opcoes = (() => {
          try { return Array.isArray(campo.opcoes) ? campo.opcoes : JSON.parse(campo.opcoes || '[]'); }
          catch { return []; }
        })();
        const opts = opcoes.map(o => `<option value="${escHtml(o)}">${escHtml(o)}</option>`).join('');
        return `<select class="form-control" id="${id}" ${req}>
                  <option value="">— Selecione —</option>
                  ${opts}
                </select>`;

      case 'checkbox':
        return `<label class="form-check">
                  <input type="checkbox" class="form-check-input" id="${id}">
                  <span>Marque se aplicável</span>
                </label>`;

      default: // text
        return `<input class="form-control" type="text" id="${id}"
                       autocapitalize="characters" spellcheck="false"
                       placeholder="${escHtml(campo.label)}" ${req}>`;
    }
  }

  function updateProgress() {
    if (!_currentTemplate) return;
    const total  = _currentTemplate.campos.length;
    const filled = _currentTemplate.campos.filter(c => {
      const el = document.getElementById(`field-${c.id}`);
      if (!el) return false;
      return c.tipo_campo === 'checkbox' ? el.checked : el.value.trim().length > 0;
    }).length;
    const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
    const bar = document.getElementById('form-progress-bar');
    if (bar) bar.style.width = `${pct}%`;
  }

  // Atualiza barra de progresso ao digitar
  document.addEventListener('input', e => {
    if (e.target.id && e.target.id.startsWith('field-')) updateProgress();
  });

  // ---------------------------------------------------------------------------
  // Utilitários globais para máscaras
  // ---------------------------------------------------------------------------
  window.maskCPF = function (input) {
    let v = input.value.replace(/\D/g, '').slice(0, 11);
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d)/, '$1.$2');
    v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    input.value = v;
  };

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  window.escHtml = escHtml;
  window.Forms   = Forms;

})();
