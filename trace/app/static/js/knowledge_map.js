(() => {
  const state = {
    nodes: window.__TRACE_MAP__.nodes || [],
    edges: window.__TRACE_MAP__.edges || [],
    suggestions: window.__TRACE_MAP__.suggestions || [],
    selectedDomains: new Set(),
    connectionMode: null,
    zoom: null,
    simulation: null,
    pinned: false,
  };

  const container = document.getElementById('graph-container');
  if (!container) return;
  const width = container.clientWidth || 1200;
  const height = Math.max(600, window.innerHeight - 200);

  if (!state.nodes.length) {
    container.innerHTML = '<div class="empty-map">No concepts yet. Import content to see your knowledge map.</div>';
    return;
  }

  const svg = d3
    .select(container)
    .append('svg')
    .attr('width', '100%')
    .attr('height', height)
    .style('background', 'var(--map-bg, #0A1628)');

  const g = svg.append('g');

  const defs = svg.append('defs');
  defs
    .append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#9CA3AF');

  const domainColor = (domain) => {
    const fallback = '#6EE7B7';
    if (!domain) return fallback;
    const token = domain.toLowerCase().replace(/[^a-z0-9]/g, '-');
    const cssColor = getComputedStyle(document.documentElement).getPropertyValue(`--${token}`);
    return cssColor || fallback;
  };

  const getNodeId = (ref) => (typeof ref === 'object' && ref ? ref.id : ref);
  const resolveNode = (ref) => (typeof ref === 'object' && ref ? ref : state.nodes.find((n) => n.id === ref));

  const sizeScale = d3
    .scaleSqrt()
    .domain([0, d3.max(state.nodes, (d) => d.reviews || 1) || 1])
    .range([8, 24]);

  state.simulation = d3
    .forceSimulation(state.nodes)
    .force('link', d3.forceLink(state.edges).id((d) => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide((d) => sizeScale(d.reviews || 0) + 6))
    .on('tick', ticked)
    .on('end', () => {
      state.pinned = true;
    });

  const link = g
    .append('g')
    .attr('stroke', '#9CA3AF')
    .attr('stroke-opacity', 0.6)
    .selectAll('line')
    .data(state.edges)
    .enter()
    .append('line')
    .attr('stroke-width', (d) => (d.connection_source === 'user' ? 2 : 1))
    .attr('stroke-dasharray', (d) => (d.connection_source === 'system' ? '4 2' : ''))
    .attr('marker-end', 'url(#arrow)')
    .on('mouseover', (event, d) => showEdgeTooltip(event, d))
    .on('mouseout', hideEdgeTooltip);

  const node = g
    .append('g')
    .selectAll('g')
    .data(state.nodes)
    .enter()
    .append('g')
    .call(
      d3
        .drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
    )
    .on('click', nodeClicked);

  node
    .append('circle')
    .attr('r', (d) => sizeScale(d.reviews || 0))
    .attr('fill', (d) => domainColor(d.domain))
    .attr('stroke', (d) => (d.is_mature ? '#D4AC0D' : '#fff'))
    .attr('stroke-width', (d) => (d.is_mature ? 3 : 1.5))
    .attr('class', 'map-node');

  node
    .append('text')
    .text((d) => (d.label || '').slice(0, 20))
    .attr('x', 0)
    .attr('y', (d) => sizeScale(d.reviews || 0) + 12)
    .attr('text-anchor', 'middle')
    .attr('class', 'map-label');

  function ticked() {
    link
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y);

    node.attr('transform', (d) => `translate(${d.x},${d.y})`);
  }

  const zoomBehavior = d3
    .zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform);
    });
  svg.call(zoomBehavior);
  state.zoom = zoomBehavior;

  document.getElementById('zoom-in').addEventListener('click', () => svg.transition().call(zoomBehavior.scaleBy, 1.2));
  document.getElementById('zoom-out').addEventListener('click', () => svg.transition().call(zoomBehavior.scaleBy, 0.8));
  document.getElementById('zoom-reset').addEventListener('click', () => svg.transition().call(zoomBehavior.fitExtent, [[0, 0], [width, height]]));
  document.getElementById('rerun-layout').addEventListener('click', () => {
    state.pinned = false;
    state.simulation.alpha(1).restart();
  });

  function dragstarted(event) {
    if (!event.active) state.simulation.alphaTarget(0.3).restart();
    event.subject.fx = event.subject.x;
    event.subject.fy = event.subject.y;
  }
  function dragged(event) {
    event.subject.fx = event.x;
    event.subject.fy = event.y;
  }
  function dragended(event) {
    if (!event.active) state.simulation.alphaTarget(0);
    if (state.pinned) return;
    event.subject.fx = null;
    event.subject.fy = null;
  }

  const detailPanel = document.getElementById('detail-panel');
  const suggestionsPanel = document.getElementById('suggestions-panel');
  const suggestionsToggle = document.getElementById('suggestions-toggle');
  const suggestionsCount = document.getElementById('suggestions-count');
  const edgeTooltip = document.getElementById('edge-tooltip');
  const connectionBanner = document.getElementById('connection-mode-banner');

  suggestionsCount.textContent = state.suggestions.length;

  function showEdgeTooltip(event, edge) {
    edgeTooltip.textContent = edge.relationship;
    edgeTooltip.style.display = 'block';
    edgeTooltip.style.left = `${event.pageX + 8}px`;
    edgeTooltip.style.top = `${event.pageY + 8}px`;
  }
  function hideEdgeTooltip() {
    edgeTooltip.style.display = 'none';
  }

  function nodeClicked(event, d) {
    if (state.connectionMode && state.connectionMode.source && state.connectionMode.source.id !== d.id) {
      openConnectionModal(state.connectionMode.source, d);
      return;
    }
    state.connectionMode = { source: d };
    showDetail(d);
  }

  function showDetail(nodeData) {
    const connections = state.edges.filter((e) => getNodeId(e.source) === nodeData.id || getNodeId(e.target) === nodeData.id);
    const connectedList = connections
      .map((c) => {
        const sourceId = getNodeId(c.source);
        const targetId = getNodeId(c.target);
        const otherId = sourceId === nodeData.id ? targetId : sourceId;
        const otherNode = resolveNode(otherId);
        return `<div class="d-flex justify-content-between align-items-center mb-2"><span>${otherNode ? otherNode.label : 'Concept'} <small class="text-white">${c.relationship}</small></span><button class="btn btn-link text-danger p-0" data-delete-connection="${c.id}"><i class="bi bi-trash"></i></button></div>`;
      })
      .join('');

    detailPanel.innerHTML = `
      <div class="d-flex justify-content-between align-items-start mb-3">
        <div>
          <div class="fs-5 fw-bold">${nodeData.label}</div>
          <div class="badge bg-secondary">${nodeData.domain || 'Unspecified'}</div>
        </div>
        <button class="btn btn-outline-light btn-sm" id="close-detail">Close</button>
      </div>
      <div class="mb-3 small text-white">${(nodeData.description || '').slice(0, 200)}</div>
      <div class="mb-3">
        <div class="fw-semibold mb-1">Connections</div>
        ${connectedList || '<div class="text-white small">No connections yet.</div>'}
      </div>
      <div class="d-flex gap-2">
        <a class="btn btn-outline-info btn-sm" href="${window.location.origin}/concepts/${nodeData.id}">View Concept Detail →</a>
        <button class="btn btn-primary btn-sm" id="connect-mode-btn">Connect to Another Concept</button>
      </div>
    `;
    detailPanel.classList.add('active');
    detailPanel.querySelector('#close-detail').addEventListener('click', () => detailPanel.classList.remove('active'));
    const connectBtn = detailPanel.querySelector('#connect-mode-btn');
    if (connectBtn) {
      connectBtn.addEventListener('click', () => {
        state.connectionMode = { source: nodeData };
        connectionBanner.classList.add('show');
      });
    }
    detailPanel.querySelectorAll('[data-delete-connection]').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const id = btn.getAttribute('data-delete-connection');
        if (!confirm('Delete this connection?')) return;
        const res = await fetch(`/map/connect/${id}/delete`, {
          method: 'POST',
          headers: { 'X-CSRFToken': window.__TRACE_MAP__.csrfToken },
        });
        if (res.ok) {
          state.edges = state.edges.filter((edge) => `${edge.id}` !== `${id}`);
          refreshGraph();
          showDetail(nodeData);
        }
      });
    });
  }

  function openConnectionModal(sourceNode, targetNode) {
    connectionBanner.classList.remove('show');
    const modal = document.createElement('div');
    modal.className = 'connection-modal';
    modal.innerHTML = `
      <div class="connection-modal-content">
        <div class="fw-bold mb-2">Connect ${sourceNode.label} → ${targetNode.label}</div>
        <select class="form-select form-select-sm mb-3" id="relationship-select">
          <option value="builds on">builds on</option>
          <option value="contradicts">contradicts</option>
          <option value="applies to">applies to</option>
          <option value="example of">example of</option>
          <option value="related to" selected>related to</option>
        </select>
        <div class="d-flex gap-2">
          <button class="btn btn-primary btn-sm" id="save-connection">Save Connection</button>
          <button class="btn btn-outline-light btn-sm" id="cancel-connection">Cancel</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('#cancel-connection').addEventListener('click', () => modal.remove());
    modal.querySelector('#save-connection').addEventListener('click', async () => {
      const relationship = modal.querySelector('#relationship-select').value;
      const res = await fetch('/map/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.__TRACE_MAP__.csrfToken,
        },
        body: JSON.stringify({
          concept_a_id: sourceNode.id,
          concept_b_id: targetNode.id,
          relationship_type: relationship,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        state.edges.push({
          id: data.connection_id,
          source: sourceNode.id,
          target: targetNode.id,
          relationship,
          connection_source: 'user',
        });
        refreshGraph();
      }
      modal.remove();
    });
  }

  function refreshGraph() {
    link.data(state.edges, (d) => d.id).join('line');
    state.simulation.force('link').links(state.edges);
    state.simulation.alpha(0.6).restart();
  }

  suggestionsToggle.addEventListener('click', async () => {
    suggestionsPanel.classList.toggle('active');
    if (state.suggestions.length === 0) {
      await loadSuggestions();
    }
    renderSuggestions();
  });
  document.getElementById('close-suggestions').addEventListener('click', () => suggestionsPanel.classList.remove('active'));

  async function loadSuggestions() {
    try {
      const res = await fetch('/map/suggestions');
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        state.suggestions = data;
        suggestionsCount.textContent = state.suggestions.length;
      }
    } catch (err) {
      // silent fail; keep panel usable even if network fails
    }
  }

  function renderSuggestions() {
    const list = document.getElementById('suggestions-list');
    if (!state.suggestions.length) {
      list.innerHTML = '<div class="text-white small">No pending suggestions.</div>';
      return;
    }
    list.innerHTML = state.suggestions
      .map(
        (s) => `
        <div class="suggestion-item">
          <div class="fw-semibold">${s.concept_a_name} → ${s.concept_b_name}</div>
          <div class="small text-white">${Math.round((s.score || 0) * 100)}% confidence · ${s.suggested_relationship}</div>
          <div class="d-flex gap-2 mt-2">
            <button class="btn btn-primary btn-sm" data-accept="${s.concept_a_id},${s.concept_b_id}">Accept</button>
            <button class="btn btn-outline-light btn-sm" data-dismiss="${s.concept_a_id},${s.concept_b_id}">Dismiss</button>
          </div>
        </div>`
      )
      .join('');

    list.querySelectorAll('[data-accept]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const [a, b] = btn.getAttribute('data-accept').split(',').map((n) => parseInt(n, 10));
        const source = state.nodes.find((n) => n.id === a);
        const target = state.nodes.find((n) => n.id === b);
        openConnectionModal(source, target);
        acceptSuggestion(a, b, 'related to');
      });
    });
    list.querySelectorAll('[data-dismiss]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const [a, b] = btn.getAttribute('data-dismiss').split(',').map((n) => parseInt(n, 10));
        await fetch('/map/suggestions/dismiss', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.__TRACE_MAP__.csrfToken },
          body: JSON.stringify({ concept_a_id: a, concept_b_id: b }),
        });
        state.suggestions = state.suggestions.filter((s) => !(s.concept_a_id === a && s.concept_b_id === b));
        suggestionsCount.textContent = state.suggestions.length;
        renderSuggestions();
      });
    });
  }

  async function acceptSuggestion(a, b, relationship) {
    await fetch('/map/suggestions/accept', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.__TRACE_MAP__.csrfToken },
      body: JSON.stringify({ concept_a_id: a, concept_b_id: b, relationship_type: relationship }),
    });
    state.suggestions = state.suggestions.filter((s) => !(s.concept_a_id === a && s.concept_b_id === b));
    suggestionsCount.textContent = state.suggestions.length;
    renderSuggestions();
  }

  document.getElementById('map-search').addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    node.classed('faded', (d) => term && !d.label.toLowerCase().includes(term));
    link.classed('faded', (d) => {
      if (!term) return false;
      const aNode = resolveNode(d.source);
      const bNode = resolveNode(d.target);
      const a = aNode && aNode.label ? aNode.label.toLowerCase().includes(term) : false;
      const b = bNode && bNode.label ? bNode.label.toLowerCase().includes(term) : false;
      return !(a || b);
    });
  });

  document.querySelectorAll('#domain-pill-group button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const domain = btn.getAttribute('data-domain');
      if (domain === 'all') {
        state.selectedDomains.clear();
        document.querySelectorAll('#domain-pill-group button').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      } else {
        document.querySelectorAll('#domain-pill-group button[data-domain="all"]').forEach((b) => b.classList.remove('active'));
        if (state.selectedDomains.has(domain)) {
          state.selectedDomains.delete(domain);
          btn.classList.remove('active');
        } else {
          state.selectedDomains.add(domain);
          btn.classList.add('active');
        }
      }
      applyDomainFilter();
    });
  });

  function applyDomainFilter() {
    if (state.selectedDomains.size === 0) {
      node.classed('faded', false);
      link.classed('faded', false);
      return;
    }
    node.classed('faded', (d) => !state.selectedDomains.has(d.domain));
    link.classed('faded', (d) => {
      const sourceNode = resolveNode(d.source);
      const targetNode = resolveNode(d.target);
      return !(
        sourceNode && targetNode && state.selectedDomains.has(sourceNode.domain) && state.selectedDomains.has(targetNode.domain)
      );
    });
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      state.connectionMode = null;
      connectionBanner.classList.remove('show');
    }
  });
})();
