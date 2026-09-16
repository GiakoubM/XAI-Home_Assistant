class ModelRelationshipCard extends HTMLElement {
  constructor() {
    super();
    this._nodes = [];
    this._edges = [];
    this._selected = null;
    this._connectMode = false;
    this._connectFrom = null;
    this._drag = null;
    this._resize = null;
    this._nextN = 1;
    this._nextE = 1;
    this._initialized = false;
    this._editMode = false;
    this._hasLoaded = false;
    this._openPanelId = null;
  }

  setConfig(config) {
    this._config = config || {};
    this._height = this._config.height || 420;
    this._ensureInit();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._hasLoaded && hass && hass.connection) {
      this._hasLoaded = true;
      this._loadFromBackend();
    }
  }

  getCardSize() {
    return Math.ceil((this._height || 420) / 50) + 1;
  }

  connectedCallback() {
    this._ensureInit();
  }

  static getStubConfig() {
    return { title: 'Model relationships', height: 420 };
  }

  _ensureInit() {
    if (this._initialized) return;
    this._initialized = true;
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          border: 1px solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
          box-shadow: var(--ha-card-box-shadow, none);
          overflow: hidden;
          font-family: var(--paper-font-body1_-_font-family, sans-serif);
        }
        .toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          flex-wrap: wrap;
        }
        .title {
          font-size: 16px;
          font-weight: 500;
          color: var(--primary-text-color, #212121);
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        button {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 13px;
          font-family: inherit;
          color: var(--primary-text-color, #212121);
          background: var(--secondary-background-color, #f0f0f0);
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 8px;
          padding: 6px 10px;
          cursor: pointer;
        }
        button:hover { filter: brightness(0.96); }
        button:disabled { opacity: 0.4; cursor: default; }
        button.active, button.edit-btn.on {
          background: var(--primary-color, #03a9f4);
          border-color: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
        }
        .hint {
          font-size: 12px;
          color: var(--secondary-text-color, #727272);
          margin-left: 4px;
        }
        .canvas-wrap {
          position: relative;
          outline: none;
        }
        .placeholder {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          color: var(--secondary-text-color, #727272);
          pointer-events: none;
          text-align: center;
          padding: 0 24px;
        }
        svg { display: block; width: 100%; }
        .node-group rect { fill: var(--card-background-color, #fff); }
        .node-group text { fill: var(--primary-text-color, #212121); }
        .edit-panel {
          position: absolute;
          display: flex;
          flex-direction: column;
          gap: 6px;
          width: 260px;
          max-height: 420px;
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 8px;
          padding: 8px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.2));
          z-index: 5;
        }
        .edit-panel .ep-scroll {
          display: flex;
          flex-direction: column;
          gap: 6px;
          overflow-y: auto;
          max-height: 220px;
          padding-right: 2px;
        }
        .edit-panel input {
          font-size: 12px;
          font-family: inherit;
          padding: 5px 6px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          box-sizing: border-box;
          width: 100%;
          color: var(--primary-text-color, #212121);
          background: var(--card-background-color, #fff);
        }
        .edit-panel .ep-size-row {
          display: flex;
          gap: 8px;
        }
        .edit-panel .ep-size-row label {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: var(--secondary-text-color, #727272);
        }
        .edit-panel .ep-size-row input {
          width: 100%;
        }
        .edit-panel .ep-section-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.02em;
          color: var(--secondary-text-color, #727272);
          margin-top: 2px;
        }
        .edit-panel .ep-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }
        .edit-panel .ep-chip {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          background: var(--secondary-background-color, #f0f0f0);
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 12px;
          padding: 2px 4px 2px 8px;
          color: var(--primary-text-color, #212121);
        }
        .edit-panel .ep-chip button {
          all: unset;
          cursor: pointer;
          font-size: 12px;
          line-height: 1;
          padding: 2px 4px;
          color: var(--secondary-text-color, #727272);
        }
        .edit-panel .ep-search-results {
          display: none;
          flex-direction: column;
          max-height: 150px;
          overflow-y: auto;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          margin-top: 2px;
        }
        .edit-panel .ep-search-results.open { display: flex; }
        .edit-panel .ep-search-result {
          padding: 5px 6px;
          cursor: pointer;
        }
        .edit-panel .ep-search-result:hover,
        .edit-panel .ep-search-result.active {
          background: var(--secondary-background-color, #f0f0f0);
        }
        .edit-panel .ep-result-name {
          font-size: 12px;
          color: var(--primary-text-color, #212121);
        }
        .edit-panel .ep-result-id {
          font-size: 10px;
          color: var(--secondary-text-color, #727272);
        }
        .edit-panel .ep-subview-status {
          font-size: 11px;
          color: var(--secondary-text-color, #727272);
        }
        .edit-panel .ep-subview-status.error { color: var(--error-color, #db4437); }
        .edit-panel .ep-actions {
          display: flex;
          justify-content: flex-end;
          gap: 6px;
          margin-top: 2px;
        }
        .edit-panel .ep-actions button {
          padding: 4px 8px;
          font-size: 12px;
        }
      </style>
      <div class="card">
        <div class="toolbar">
          <span class="title"></span>
          <span class="hint"></span>
          <button class="add-btn">+ Model</button>
          <button class="connect-btn">Connect</button>
          <button class="del-btn" disabled>Delete</button>
          <button class="edit-btn">Edit</button>
        </div>
        <div class="canvas-wrap" tabindex="0">
          <svg viewBox="0 0 680 ${this._height || 420}" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker id="rc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--secondary-text-color, #727272)"></path>
              </marker>
            </defs>
          </svg>
          <div class="placeholder"></div>
        </div>
      </div>
    `;
    this._els = {
      title: this.shadowRoot.querySelector('.title'),
      hint: this.shadowRoot.querySelector('.hint'),
      addBtn: this.shadowRoot.querySelector('.add-btn'),
      connectBtn: this.shadowRoot.querySelector('.connect-btn'),
      delBtn: this.shadowRoot.querySelector('.del-btn'),
      editBtn: this.shadowRoot.querySelector('.edit-btn'),
      wrap: this.shadowRoot.querySelector('.canvas-wrap'),
      svg: this.shadowRoot.querySelector('svg'),
      placeholder: this.shadowRoot.querySelector('.placeholder'),
    };
    this._W = (this._config && this._config.box_width) || 140;
    this._H = (this._config && this._config.box_height) || 56;

    this._els.addBtn.addEventListener('click', () => this._addNode());
    this._els.connectBtn.addEventListener('click', () => this._toggleConnect());
    this._els.delBtn.addEventListener('click', () => this._deleteSelected());
    this._els.editBtn.addEventListener('click', () => this._toggleEditMode());
    this._els.svg.addEventListener('pointerdown', (e) => this._onPointerDown(e));
    this._els.svg.addEventListener('pointermove', (e) => this._onPointerMove(e));
    this._els.svg.addEventListener('pointerup', (e) => this._onPointerUp(e));
    this._els.svg.addEventListener('pointercancel', (e) => this._onPointerUp(e));
    this._els.svg.addEventListener('click', (e) => this._onCanvasClick(e));
    this._els.svg.addEventListener('dblclick', (e) => this._onDblClick(e));
    this._els.wrap.addEventListener('keydown', (e) => {
      const t = e.target;
      const isFormField = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      if (isFormField) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && this._selected && this._editMode) {
        e.preventDefault();
        this._deleteSelected();
      }
    });
  }

  _maxIdNumber(items, prefix) {
    let max = 0;
    items.forEach((item) => {
      if (typeof item.id === 'string' && item.id.startsWith(prefix)) {
        const n = parseInt(item.id.slice(prefix.length), 10);
        if (!isNaN(n) && n > max) max = n;
      }
    });
    return max;
  }

  _dedupeIds(items, prefix) {
    let changed = false;
    let counter = this._maxIdNumber(items, prefix) + 1;
    const seen = new Set();
    items.forEach((item) => {
      if (typeof item.id !== 'string') return;
      if (seen.has(item.id)) {
        item.id = prefix + (counter++);
        changed = true;
      }
      seen.add(item.id);
    });
    return changed;
  }

  async _loadFromBackend() {
    try {
      const data = await this._hass.connection.sendMessagePromise({ type: 'model_relationships/get' });
      this._nodes = data.nodes || [];
      this._edges = data.edges || [];
      const nodesRepaired = this._dedupeIds(this._nodes, 'n');
      const edgesRepaired = this._dedupeIds(this._edges, 'e');
      this._nextN = this._maxIdNumber(this._nodes, 'n') + 1;
      this._nextE = this._maxIdNumber(this._edges, 'e') + 1;
      if (nodesRepaired || edgesRepaired) this._save();
    } catch (err) {
      this._els.hint.textContent = 'Could not reach the model_relationships integration \u2014 is it installed?';
    }
    this._render();
  }

  _save() {
    if (!this._hass || !this._hass.connection) return Promise.resolve();
    return this._hass.connection.sendMessagePromise({
      type: 'model_relationships/save',
      nodes: this._nodes,
      edges: this._edges,
    }).catch(() => {});
  }

  _dashboardBase() {
    const parts = window.location.pathname.split('/').filter(Boolean);
    return parts.length ? '/' + parts[0] : '';
  }

  _navigate(target) {
    if (!target) return;
    let path = target.trim();
    if (!path) return;
    if (!path.startsWith('/')) {
      path = this._dashboardBase() + '/' + path;
    }
    history.pushState(null, '', path);
    const event = new Event('location-changed', { bubbles: true, composed: true });
    window.dispatchEvent(event);
  }

  _nodeById(id) {
    return this._nodes.find((n) => n.id === id);
  }

  _edgePoint(cx, cy, hw, hh, tx, ty) {
    const dx = tx - cx;
    const dy = ty - cy;
    if (dx === 0 && dy === 0) return [cx, cy];
    const sx = dx !== 0 ? hw / Math.abs(dx) : Infinity;
    const sy = dy !== 0 ? hh / Math.abs(dy) : Infinity;
    const s = Math.min(sx, sy);
    return [cx + dx * s, cy + dy * s];
  }

  _render() {
    this._els.title.textContent = this._config.title || '';
    this._els.title.style.display = this._config.title ? '' : 'none';
    this._els.placeholder.style.display = this._nodes.length === 0 ? '' : 'none';
    this._els.placeholder.textContent = this._editMode
      ? 'Click "+ Model" to add your first model'
      : 'Click "Edit" to start building your diagram';

    this._els.addBtn.style.display = this._editMode ? '' : 'none';
    this._els.connectBtn.style.display = this._editMode ? '' : 'none';
    this._els.delBtn.style.display = this._editMode ? '' : 'none';
    this._els.editBtn.textContent = this._editMode ? 'Done' : 'Edit';
    this._els.editBtn.classList.toggle('on', this._editMode);

    const svg = this._els.svg;
    svg.querySelectorAll('.edge-wrap, .node-group, .edge-badge').forEach((el) => el.remove());

    this._edges.forEach((edge) => {
      const a = this._nodeById(edge.from), b = this._nodeById(edge.to);
      if (!a || !b) return;
      const aW = a.w || this._W, aH = a.h || this._H, bW = b.w || this._W, bH = b.h || this._H;
      const acx = a.x + aW / 2, acy = a.y + aH / 2, bcx = b.x + bW / 2, bcy = b.y + bH / 2;
      const p1 = this._edgePoint(acx, acy, aW / 2, aH / 2, bcx, bcy);
      const p2 = this._edgePoint(bcx, bcy, bW / 2, bH / 2, acx, acy);
      const shared = (a.outputs || []).filter((eid) => (b.inputs || []).includes(eid));

      const wrap = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      wrap.setAttribute('class', 'edge-wrap');
      wrap.setAttribute('data-id', edge.id);
      if (this._editMode) wrap.style.cursor = 'pointer';

      // Invisible fat line: the actual click/tap target, much easier to
      // hit than the thin visible line underneath it.
      const hit = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      hit.setAttribute('class', 'edge-hit');
      hit.setAttribute('x1', p1[0]); hit.setAttribute('y1', p1[1]);
      hit.setAttribute('x2', p2[0]); hit.setAttribute('y2', p2[1]);
      hit.setAttribute('stroke', 'transparent');
      hit.setAttribute('stroke-width', '16');
      hit.style.pointerEvents = this._editMode ? 'stroke' : 'none';
      wrap.appendChild(hit);

      const isSel = this._editMode && this._selected && this._selected.type === 'edge' && this._selected.id === edge.id;
      let stroke = 'var(--divider-color, #bdbdbd)';
      if (shared.length) stroke = 'var(--success-color, #43a047)';
      if (isSel) stroke = 'var(--primary-color, #03a9f4)';
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('class', 'edge');
      line.setAttribute('x1', p1[0]); line.setAttribute('y1', p1[1]);
      line.setAttribute('x2', p2[0]); line.setAttribute('y2', p2[1]);
      line.setAttribute('stroke', stroke);
      line.setAttribute('stroke-width', isSel ? '2.5' : '1.5');
      line.setAttribute('marker-end', 'url(#rc-arrow)');
      line.style.pointerEvents = 'none';
      if (shared.length) {
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = shared.map((eid) => this._entityLabel(eid)).join(', ');
        line.appendChild(title);
      }
      wrap.appendChild(line);
      svg.appendChild(wrap);

      if (shared.length) {
        svg.appendChild(this._buildEdgeBadge(edge.id, p1, p2, shared));
      }
    });

    this._nodes.forEach((n) => {
      const w = n.w || this._W, h = n.h || this._H;
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', 'node-group');
      g.setAttribute('data-id', n.id);
      g.setAttribute('transform', `translate(${n.x},${n.y})`);
      const isSel = this._editMode && this._selected && this._selected.type === 'node' && this._selected.id === n.id;
      const isSrc = this._connectFrom === n.id;
      if (this._editMode) {
        g.style.cursor = this._connectMode ? 'crosshair' : 'grab';
      } else {
        g.style.cursor = n.navigate ? 'pointer' : 'default';
      }
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('class', 'node-rect');
      rect.setAttribute('width', w); rect.setAttribute('height', h); rect.setAttribute('rx', 8);
      rect.setAttribute('stroke', isSel || isSrc ? 'var(--primary-color, #03a9f4)' : 'var(--divider-color, #bdbdbd)');
      rect.setAttribute('stroke-width', isSel || isSrc ? '2' : '1');
      g.appendChild(rect);
      const clipId = 'clip-' + n.id;
      const clipPath = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
      clipPath.setAttribute('id', clipId);
      const clipRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      clipRect.setAttribute('width', w); clipRect.setAttribute('height', h); clipRect.setAttribute('rx', 8);
      clipPath.appendChild(clipRect);
      g.appendChild(clipPath);
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('class', 'node-label');
      text.setAttribute('x', w / 2); text.setAttribute('y', h / 2 + 1);
      text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'middle');
      text.setAttribute('font-size', String(this._fitFontSize(n.label, w, h))); text.setAttribute('font-weight', '500');
      text.setAttribute('clip-path', `url(#${clipId})`);
      text.textContent = n.label;
      g.appendChild(text);
      const icon = this._iconMetrics(w, h);
      if (n.navigate) {
        const mark = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        mark.setAttribute('class', 'nav-mark');
        mark.setAttribute('x', w - icon.pad); mark.setAttribute('y', icon.pad);
        mark.setAttribute('text-anchor', 'middle'); mark.setAttribute('font-size', String(icon.fontSize));
        mark.setAttribute('fill', 'var(--secondary-text-color, #727272)');
        mark.textContent = '\u2197';
        g.appendChild(mark);
      }
      if (this._editMode && !this._connectMode) {
        const iconBg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        iconBg.setAttribute('class', 'edit-icon');
        iconBg.setAttribute('cx', icon.pad); iconBg.setAttribute('cy', icon.pad); iconBg.setAttribute('r', icon.r);
        iconBg.setAttribute('fill', 'var(--secondary-background-color, #f0f0f0)');
        iconBg.setAttribute('stroke', 'var(--divider-color, #bdbdbd)');
        iconBg.setAttribute('stroke-width', '1');
        iconBg.style.cursor = 'pointer';
        g.appendChild(iconBg);
        const iconText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        iconText.setAttribute('x', icon.pad); iconText.setAttribute('y', icon.pad + 1);
        iconText.setAttribute('text-anchor', 'middle'); iconText.setAttribute('dominant-baseline', 'middle');
        iconText.setAttribute('font-size', String(icon.fontSize));
        iconText.setAttribute('fill', 'var(--primary-text-color, #212121)');
        iconText.style.pointerEvents = 'none';
        iconText.textContent = '\u270E';
        g.appendChild(iconText);
      }
      if (this._editMode && !this._connectMode && this._openPanelId === n.id) {
        Object.entries(this._handlePositions(w, h)).forEach(([key, pos]) => {
          const handle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          handle.setAttribute('class', 'resize-handle');
          handle.setAttribute('data-handle', key);
          handle.setAttribute('cx', pos[0]); handle.setAttribute('cy', pos[1]);
          handle.setAttribute('r', 5);
          handle.setAttribute('fill', 'var(--card-background-color, #fff)');
          handle.setAttribute('stroke', 'var(--primary-color, #03a9f4)');
          handle.setAttribute('stroke-width', '1.5');
          handle.style.cursor = (key === 'n' || key === 's') ? 'ns-resize'
            : (key === 'e' || key === 'w') ? 'ew-resize'
            : (key === 'nw' || key === 'se') ? 'nwse-resize' : 'nesw-resize';
          g.appendChild(handle);
        });
      }
      svg.appendChild(g);
    });

    this._els.delBtn.disabled = !this._selected;
    this._els.connectBtn.classList.toggle('active', this._connectMode);
    if (this._editMode && this._connectMode) {
      this._els.hint.textContent = this._connectFrom ? 'Click the target model' : 'Click a model to start a connection';
    } else {
      this._els.hint.textContent = '';
    }
  }

  _updateNodePosition(id) {
    const n = this._nodeById(id);
    const svg = this._els.svg;
    const g = svg.querySelector(`.node-group[data-id="${id}"]`);
    if (g) g.setAttribute('transform', `translate(${n.x},${n.y})`);
    this._updateEdgesForNode(id);
    if (this._openPanelId === id) this._positionPanelFor(id);
  }

  _updateEdgesForNode(id) {
    const svg = this._els.svg;
    this._edges.forEach((edge) => {
      if (edge.from !== id && edge.to !== id) return;
      const a = this._nodeById(edge.from), b = this._nodeById(edge.to);
      const aW = a.w || this._W, aH = a.h || this._H, bW = b.w || this._W, bH = b.h || this._H;
      const acx = a.x + aW / 2, acy = a.y + aH / 2, bcx = b.x + bW / 2, bcy = b.y + bH / 2;
      const p1 = this._edgePoint(acx, acy, aW / 2, aH / 2, bcx, bcy);
      const p2 = this._edgePoint(bcx, bcy, bW / 2, bH / 2, acx, acy);
      const wrap = svg.querySelector(`.edge-wrap[data-id="${edge.id}"]`);
      if (wrap) {
        wrap.querySelectorAll('line').forEach((ln) => {
          ln.setAttribute('x1', p1[0]); ln.setAttribute('y1', p1[1]);
          ln.setAttribute('x2', p2[0]); ln.setAttribute('y2', p2[1]);
        });
      }
      const badge = svg.querySelector(`.edge-badge[data-id="${edge.id}"]`);
      if (badge) {
        const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2;
        const bg = badge.querySelector('rect');
        const approxW = bg ? parseFloat(bg.getAttribute('width')) : 60;
        badge.setAttribute('transform', `translate(${mx - approxW / 2},${my - 5})`);
      }
    });
  }

  _fitFontSize(label, w, h) {
    const byHeight = h * 0.24;
    const byWidth = label && label.length ? (w - 12) / (label.length * 0.55) : byHeight;
    return Math.max(8, Math.min(13, Math.floor(Math.min(byHeight, byWidth))));
  }

  _iconMetrics(w, h) {
    const base = Math.min(w, h);
    const r = Math.max(6, Math.min(9, base * 0.16));
    return { r, fontSize: Math.max(7, Math.round(r * 1.05)), pad: r + 5 };
  }

  _handlePositions(w, h) {
    return {
      nw: [0, 0], n: [w / 2, 0], ne: [w, 0],
      w: [0, h / 2], e: [w, h / 2],
      sw: [0, h], s: [w / 2, h], se: [w, h],
    };
  }

  _updateNodeSize(id) {
    const n = this._nodeById(id);
    const svg = this._els.svg;
    const g = svg.querySelector(`.node-group[data-id="${id}"]`);
    if (!g) return;
    const w = n.w || this._W, h = n.h || this._H;
    g.setAttribute('transform', `translate(${n.x},${n.y})`);
    const rect = g.querySelector('.node-rect');
    if (rect) { rect.setAttribute('width', w); rect.setAttribute('height', h); }
    const clipRect = g.querySelector('clipPath rect');
    if (clipRect) { clipRect.setAttribute('width', w); clipRect.setAttribute('height', h); }
    const label = g.querySelector('.node-label');
    if (label) {
      label.setAttribute('x', w / 2); label.setAttribute('y', h / 2 + 1);
      label.setAttribute('font-size', String(this._fitFontSize(n.label, w, h)));
    }
    const icon = this._iconMetrics(w, h);
    const mark = g.querySelector('.nav-mark');
    if (mark) { mark.setAttribute('x', w - icon.pad); mark.setAttribute('y', icon.pad); mark.setAttribute('font-size', String(icon.fontSize)); }
    const editIconBg = g.querySelector('.edit-icon');
    if (editIconBg) { editIconBg.setAttribute('cx', icon.pad); editIconBg.setAttribute('cy', icon.pad); editIconBg.setAttribute('r', icon.r); }
    const editIconText = g.querySelector('.edit-icon + text');
    if (editIconText) { editIconText.setAttribute('x', icon.pad); editIconText.setAttribute('y', icon.pad + 1); editIconText.setAttribute('font-size', String(icon.fontSize)); }
    const positions = this._handlePositions(w, h);
    g.querySelectorAll('.resize-handle').forEach((handle) => {
      const pos = positions[handle.getAttribute('data-handle')];
      if (pos) { handle.setAttribute('cx', pos[0]); handle.setAttribute('cy', pos[1]); }
    });
    this._updateEdgesForNode(id);
    if (this._openPanelId === id) this._positionPanelFor(id);
  }

  _positionPanelFor(id) {
    const panel = this._els.wrap.querySelector('.edit-panel');
    if (!panel) return;
    const g = this._els.svg.querySelector(`.node-group[data-id="${id}"]`);
    if (!g) return;
    const rect = g.querySelector('.node-rect').getBoundingClientRect();
    const wrapRect = this._els.wrap.getBoundingClientRect();
    const panelH = panel.offsetHeight || 300;
    const panelW = panel.offsetWidth || 260;
    const spaceBelow = wrapRect.bottom - rect.bottom;
    const spaceAbove = rect.top - wrapRect.top;
    let top;
    if (spaceBelow >= panelH + 8 || spaceBelow >= spaceAbove) {
      top = rect.bottom - wrapRect.top + 4;
    } else {
      top = rect.top - wrapRect.top - panelH - 4;
    }
    top = Math.max(0, Math.min(top, Math.max(0, wrapRect.height - panelH)));
    let left = rect.left - wrapRect.left;
    left = Math.max(0, Math.min(left, Math.max(0, wrapRect.width - panelW)));
    panel.style.top = top + 'px';
    panel.style.left = left + 'px';
  }

  _addNode() {
    const num = this._nextN++;
    const id = 'n' + num;
    const viewW = 680, viewH = this._height || 420;
    this._nodes.push({
      id,
      label: 'Model ' + num,
      navigate: '',
      inputs: [],
      outputs: [],
      x: Math.max(10, Math.random() * (viewW - this._W - 20) + 10),
      y: Math.max(10, Math.random() * (viewH - this._H - 20) + 10),
    });
    this._selected = { type: 'node', id };
    this._save();
    this._render();
    this._openEditPanel(id);
  }

  _toggleConnect() {
    this._connectMode = !this._connectMode;
    this._connectFrom = null;
    if (this._connectMode) this._selected = null;
    this._render();
  }

  _toggleEditMode() {
    this._editMode = !this._editMode;
    this._connectMode = false;
    this._connectFrom = null;
    this._selected = null;
    this._render();
  }

  _deleteSelected() {
    if (!this._selected) return;
    if (this._selected.type === 'node') {
      this._nodes = this._nodes.filter((n) => n.id !== this._selected.id);
      this._edges = this._edges.filter((e) => e.from !== this._selected.id && e.to !== this._selected.id);
      if (this._openPanelId === this._selected.id) {
        const panel = this._els.wrap.querySelector('.edit-panel');
        if (panel) panel.remove();
        this._openPanelId = null;
      }
    } else {
      this._edges = this._edges.filter((e) => e.id !== this._selected.id);
    }
    this._selected = null;
    this._save();
    this._render();
  }

  _onCanvasClick(e) {
    if (this._editMode) return;
    const g = e.target.closest('.node-group');
    if (!g) return;
    const n = this._nodeById(g.getAttribute('data-id'));
    if (n && n.navigate) this._navigate(n.navigate);
  }

  _onPointerDown(e) {
    if (!this._editMode) return;
    const handleEl = e.target.closest('.resize-handle');
    if (handleEl && !this._connectMode) {
      const parentG = handleEl.closest('.node-group');
      if (!parentG) return;
      const id = parentG.getAttribute('data-id');
      const n = this._nodeById(id);
      const svg = this._els.svg;
      const pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      this._resize = {
        id,
        handle: handleEl.getAttribute('data-handle'),
        startX: n.x, startY: n.y,
        startW: n.w || this._W, startH: n.h || this._H,
        pointerX: loc.x, pointerY: loc.y,
      };
      svg.setPointerCapture(e.pointerId);
      return;
    }
    const editIcon = e.target.closest('.edit-icon');
    if (editIcon) {
      const parentG = editIcon.closest('.node-group');
      if (parentG) this._openEditPanel(parentG.getAttribute('data-id'));
      return;
    }
    const g = e.target.closest('.node-group');
    const wrapHit = e.target.closest('.edge-wrap');
    const svg = this._els.svg;
    if (g) {
      const id = g.getAttribute('data-id');
      if (this._connectMode) {
        if (!this._connectFrom) {
          this._connectFrom = id;
        } else if (this._connectFrom !== id) {
          this._edges.push({ id: 'e' + (this._nextE++), from: this._connectFrom, to: id });
          this._connectFrom = null;
          this._save();
        }
        this._render();
        return;
      }
      this._selected = { type: 'node', id };
      const n = this._nodeById(id);
      const pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      this._drag = { id, dx: loc.x - n.x, dy: loc.y - n.y };
      svg.setPointerCapture(e.pointerId);
      this._render();
      return;
    }
    if (wrapHit) {
      if (this._connectMode) return;
      this._selected = { type: 'edge', id: wrapHit.getAttribute('data-id') };
      this._render();
      return;
    }
    if (!this._connectMode) {
      this._selected = null;
    } else {
      this._connectFrom = null;
    }
    this._render();
  }

  _onPointerMove(e) {
    if (!this._editMode) return;
    if (this._resize) {
      const svg = this._els.svg;
      const pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const dx = loc.x - this._resize.pointerX;
      const dy = loc.y - this._resize.pointerY;
      const { startX, startY, startW, startH, handle, id } = this._resize;
      const minW = 40, minH = 20;
      let newX = startX, newY = startY, newW = startW, newH = startH;
      if (handle.includes('e')) newW = Math.max(minW, startW + dx);
      if (handle.includes('w')) { newW = Math.max(minW, startW - dx); newX = startX + (startW - newW); }
      if (handle.includes('s')) newH = Math.max(minH, startH + dy);
      if (handle.includes('n')) { newH = Math.max(minH, startH - dy); newY = startY + (startH - newH); }
      const n = this._nodeById(id);
      n.x = newX; n.y = newY; n.w = newW; n.h = newH;
      this._updateNodeSize(id);
      return;
    }
    if (!this._drag) return;
    const svg = this._els.svg;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    const n = this._nodeById(this._drag.id);
    n.x = loc.x - this._drag.dx;
    n.y = loc.y - this._drag.dy;
    this._updateNodePosition(this._drag.id);
  }

  _onPointerUp(e) {
    if (e && e.pointerId !== undefined && this._els.svg.hasPointerCapture && this._els.svg.hasPointerCapture(e.pointerId)) {
      try { this._els.svg.releasePointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    }
    if (this._resize) {
      const id = this._resize.id;
      this._resize = null;
      this._save();
      this._render();
      if (this._openPanelId === id) {
        const panel = this._els.wrap.querySelector('.edit-panel');
        const n = this._nodeById(id);
        if (panel && n) {
          const wIn = panel.querySelector('.ep-width');
          const hIn = panel.querySelector('.ep-height');
          if (wIn) wIn.value = n.w || this._W;
          if (hIn) hIn.value = n.h || this._H;
        }
        this._positionPanelFor(id);
      }
      return;
    }
    if (this._drag) {
      this._drag = null;
      this._save();
    }
  }

  _onDblClick(e) {
    if (!this._editMode) return;
    const g = e.target.closest('.node-group');
    if (!g) return;
    this._openEditPanel(g.getAttribute('data-id'));
  }

  _openEditPanel(id) {
    const existing = this._els.wrap.querySelector('.edit-panel');
    if (existing) existing.remove();
    const n = this._nodeById(id);
    if (!n) return;
    const g = this._els.svg.querySelector(`.node-group[data-id="${id}"]`);
    if (!g) return;

    let inputs = (n.inputs || []).slice();
    let outputs = (n.outputs || []).slice();

    const panel = document.createElement('div');
    panel.className = 'edit-panel';
    panel.innerHTML =
      '<input class="ep-label" type="text" placeholder="Label" />' +
      '<input class="ep-path" type="text" placeholder="subview path, e.g. climate (optional)" />' +
      '<div class="ep-size-row">' +
      '<label>W <input class="ep-width" type="number" min="60" step="10" /></label>' +
      '<label>H <input class="ep-height" type="number" min="30" step="10" /></label>' +
      '</div>' +
      '<div class="ep-scroll">' +
      '<div class="ep-section-label">Inputs</div>' +
      '<div class="ep-chips ep-inputs-chips"></div>' +
      '<div class="ep-inputs-picker"></div>' +
      '<div class="ep-section-label">Outputs</div>' +
      '<div class="ep-chips ep-outputs-chips"></div>' +
      '<div class="ep-outputs-picker"></div>' +
      '</div>' +
      '<div class="ep-subview-status"></div>' +
      '<div class="ep-actions"><button type="button" class="ep-cancel">Cancel</button>' +
      '<button type="button" class="ep-subview">Create subview</button>' +
      '<button type="button" class="ep-save">Save</button></div>';
    this._els.wrap.appendChild(panel);
    this._openPanelId = id;
    this._positionPanelFor(id);

    const labelInput = panel.querySelector('.ep-label');
    const pathInput = panel.querySelector('.ep-path');
    const widthInput = panel.querySelector('.ep-width');
    const heightInput = panel.querySelector('.ep-height');
    const statusEl = panel.querySelector('.ep-subview-status');
    labelInput.value = n.label;
    pathInput.value = n.navigate || '';
    widthInput.value = n.w || this._W;
    heightInput.value = n.h || this._H;
    const applySize = () => {
      const w = parseInt(widthInput.value, 10);
      const h = parseInt(heightInput.value, 10);
      if (!isNaN(w) && w >= 40) n.w = w;
      if (!isNaN(h) && h >= 20) n.h = h;
      this._render();
      this._positionPanelFor(id);
    };
    widthInput.addEventListener('input', applySize);
    heightInput.addEventListener('input', applySize);

    const inputsChips = panel.querySelector('.ep-inputs-chips');
    const outputsChips = panel.querySelector('.ep-outputs-chips');
    const renderInputChips = () => this._renderChips(inputsChips, inputs, (entityId) => {
      inputs = inputs.filter((e) => e !== entityId);
      renderInputChips();
    });
    const renderOutputChips = () => this._renderChips(outputsChips, outputs, (entityId) => {
      outputs = outputs.filter((e) => e !== entityId);
      renderOutputChips();
    });
    renderInputChips();
    renderOutputChips();

    this._mountEntityPicker(panel.querySelector('.ep-inputs-picker'), (entityId) => {
      if (!inputs.includes(entityId)) inputs.push(entityId);
      renderInputChips();
    });
    this._mountEntityPicker(panel.querySelector('.ep-outputs-picker'), (entityId) => {
      if (!outputs.includes(entityId)) outputs.push(entityId);
      renderOutputChips();
    });

    let done = false;
    const close = () => {
      if (done) return;
      done = true;
      this._openPanelId = null;
      if (panel.parentNode) panel.remove();
    };
    const commit = () => {
      if (done) return;
      n.label = labelInput.value.trim() || n.label;
      n.navigate = pathInput.value.trim();
      n.inputs = inputs;
      n.outputs = outputs;
      close();
      this._save();
      this._render();
    };

    panel.querySelector('.ep-save').addEventListener('click', commit);
    panel.querySelector('.ep-cancel').addEventListener('click', close);
    panel.querySelector('.ep-subview').addEventListener('click', async () => {
      if (!this._hass || !this._hass.connection) {
        statusEl.classList.add('error');
        statusEl.textContent = 'Not connected to Home Assistant';
        return;
      }
      statusEl.classList.remove('error');
      statusEl.textContent = 'Saving\u2026';

      // If you've typed a path, that's what becomes the subview's
      // actual path (and what this box navigates to) - we only
      // fall back to the auto-generated model-<id> when the field
      // is left blank. Any slashes you typed are collapsed down to
      // the last segment, since a Lovelace view's own path has to
      // be a single clean slug.
      const typed = pathInput.value.trim();
      let viewPath = 'model-' + id;
      if (typed) {
        const segments = typed.split('/').filter(Boolean);
        if (segments.length) viewPath = segments[segments.length - 1];
      }
      n.label = labelInput.value.trim() || n.label;
      n.navigate = viewPath;
      n.inputs = inputs;
      n.outputs = outputs;
      pathInput.value = viewPath;
      await this._save();

      statusEl.textContent = 'Creating subview\u2026';
      try {
        await this._hass.connection.sendMessagePromise({
          type: 'model_relationships/create_view',
          dashboard: this._dashboardBase().replace(/^\//, ''),
          model_id: id,
          title: n.label,
          inputs,
          outputs,
        });
        if (statusEl.isConnected) {
          statusEl.textContent = 'Subview created at "' + viewPath + '" \u2014 click "Done" to exit editing, then click this box to go there';
        }
        this._render();
        this._positionPanelFor(id);
      } catch (err) {
        if (statusEl.isConnected) {
          statusEl.classList.add('error');
          statusEl.textContent = (err && err.message) || 'Could not create the subview';
        }
      }
    });

    labelInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') commit(); });
    pathInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') commit(); });
    panel.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Escape') close();
    });

    labelInput.focus();
    labelInput.select();
  }

  _entityLabel(entityId) {
    const state = this._hass && this._hass.states && this._hass.states[entityId];
    return (state && state.attributes && state.attributes.friendly_name) || entityId;
  }

  _buildEdgeBadge(edgeId, p1, p2, shared) {
    const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2;
    const labelText = shared.length === 1 ? this._entityLabel(shared[0]) : shared.length + ' shared';
    const approxW = Math.min(84, Math.max(16, labelText.length * 4 + 6));
    const badge = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    badge.setAttribute('class', 'edge-badge');
    badge.setAttribute('data-id', edgeId);
    badge.setAttribute('transform', `translate(${mx - approxW / 2},${my - 5})`);
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', approxW); bg.setAttribute('height', 10); bg.setAttribute('rx', 5);
    bg.setAttribute('fill', 'var(--card-background-color, #fff)');
    bg.setAttribute('stroke', 'var(--success-color, #43a047)');
    bg.setAttribute('stroke-width', '1');
    badge.appendChild(bg);
    const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txt.setAttribute('x', approxW / 2); txt.setAttribute('y', 6);
    txt.setAttribute('text-anchor', 'middle'); txt.setAttribute('dominant-baseline', 'middle');
    txt.setAttribute('font-size', '6');
    txt.setAttribute('fill', 'var(--primary-text-color, #212121)');
    txt.textContent = labelText;
    badge.appendChild(txt);
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = shared.map((eid) => this._entityLabel(eid)).join(', ');
    badge.appendChild(title);
    return badge;
  }

  _renderChips(container, list, onRemove) {
    container.innerHTML = '';
    list.forEach((entityId) => {
      const chip = document.createElement('span');
      chip.className = 'ep-chip';
      const label = document.createElement('span');
      label.textContent = this._entityLabel(entityId);
      chip.appendChild(label);
      const rm = document.createElement('button');
      rm.type = 'button';
      rm.textContent = '\u00d7';
      rm.addEventListener('click', () => onRemove(entityId));
      chip.appendChild(rm);
      container.appendChild(chip);
    });
  }

  _mountEntityPicker(container, onAdd) {
    container.innerHTML =
      '<input class="ep-search-input" type="text" placeholder="Search by name or entity id" />' +
      '<div class="ep-search-results"></div>';
    const input = container.querySelector('.ep-search-input');
    const results = container.querySelector('.ep-search-results');
    let matches = [];
    let activeIndex = -1;

    const closeResults = () => {
      results.classList.remove('open');
      results.innerHTML = '';
      matches = [];
      activeIndex = -1;
    };

    const renderResults = () => {
      results.innerHTML = '';
      matches.forEach((m, i) => {
        const row = document.createElement('div');
        row.className = 'ep-search-result' + (i === activeIndex ? ' active' : '');
        const name = document.createElement('div');
        name.className = 'ep-result-name';
        name.textContent = m.name;
        row.appendChild(name);
        const idEl = document.createElement('div');
        idEl.className = 'ep-result-id';
        idEl.textContent = m.entityId;
        row.appendChild(idEl);
        // mousedown (not click) + preventDefault so this fires before
        // the input's blur handler would otherwise close the list first
        row.addEventListener('mousedown', (e) => {
          e.preventDefault();
          onAdd(m.entityId);
          input.value = '';
          closeResults();
        });
        results.appendChild(row);
      });
      results.classList.toggle('open', matches.length > 0);
    };

    const search = (term) => {
      const q = term.trim().toLowerCase();
      if (!q || !this._hass || !this._hass.states) {
        closeResults();
        return;
      }
      matches = Object.keys(this._hass.states)
        .map((entityId) => ({ entityId, name: this._entityLabel(entityId) }))
        .filter((m) => m.entityId.toLowerCase().includes(q) || m.name.toLowerCase().includes(q))
        .slice(0, 8);
      activeIndex = -1;
      renderResults();
    };

    input.addEventListener('input', () => search(input.value));
    input.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (matches.length) { activeIndex = (activeIndex + 1) % matches.length; renderResults(); }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (matches.length) { activeIndex = (activeIndex - 1 + matches.length) % matches.length; renderResults(); }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const pick = matches[activeIndex] || matches[0];
        if (pick) {
          onAdd(pick.entityId);
          input.value = '';
          closeResults();
        }
      } else if (e.key === 'Escape') {
        closeResults();
      }
    });
    input.addEventListener('blur', () => setTimeout(closeResults, 150));
  }
}

customElements.define('model-relationship-card', ModelRelationshipCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'model-relationship-card',
  name: 'Model relationship card',
  description: 'A dynamic diagram of models and the connections between them.',
});
