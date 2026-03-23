let conceptsState = [];
let originalSourceHtml = '';

function initConcepts(data) {
  conceptsState = (data || []).map((item, idx) => ({
    id: idx,
    name: item.name || '',
    description: item.description || '',
    domain_tag: item.domain_tag || (item.domain || ''),
    source_excerpt: item.source_excerpt || '',
    action: 'pending',
    is_custom: !!item.is_custom,
  }));
  renderState();
}

function updateCounters() {
  const confirmed = conceptsState.filter((c) => c.action === 'confirmed').length;
  const rejected = conceptsState.filter((c) => c.action === 'rejected').length;
  const pending = conceptsState.filter((c) => c.action === 'pending').length;
  const badge = document.getElementById('conceptCounter');
  if (badge) badge.textContent = `${confirmed} confirmed / ${rejected} rejected / ${pending} pending`;
  updateCTAButton();
}

function updateCTAButton() {
  const cta = document.getElementById('conceptSubmitBtn');
  const confirmed = conceptsState.filter((c) => c.action === 'confirmed').length;
  const pending = conceptsState.filter((c) => c.action === 'pending').length;
  if (cta) {
    cta.disabled = pending !== 0;
    cta.textContent = pending === 0 ? `Add ${confirmed} concepts to my library` : `Review pending concepts`;
  }
}

function setCardState(card, state) {
  card.classList.remove('confirmed', 'rejected', 'editing');
  if (state === 'confirmed') card.classList.add('confirmed');
  if (state === 'rejected') card.classList.add('rejected');
  if (state === 'editing') card.classList.add('editing');
  const overlay = card.querySelector('.concept-card-overlay');
  if (overlay) overlay.classList.toggle('d-none', state !== 'confirmed');
}

function renderState() {
  const container = document.getElementById('conceptCards');
  if (!container) return;
  container.querySelectorAll('.concept-card').forEach((card) => {
    const idx = parseInt(card.dataset.index, 10);
    const concept = conceptsState[idx];
    if (!concept) return;
    setCardState(card, concept.action);
    const nameEl = card.querySelector('.concept-name');
    if (nameEl) nameEl.textContent = concept.name;
    const descEl = card.querySelector('.concept-description');
    if (descEl) descEl.textContent = concept.description;
    const excerptEl = card.querySelector('.concept-excerpt');
    if (excerptEl) excerptEl.textContent = concept.source_excerpt ? `Source: ${concept.source_excerpt.slice(0, 100)}...` : '';
    const domainEl = card.querySelector('.concept-domain');
    if (domainEl) {
      domainEl.value = concept.domain_tag || '';
      domainEl.onchange = (e) => { conceptsState[idx].domain_tag = e.target.value; };
    }
  });
  updateCounters();
}

function confirmConcept(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  conceptsState[idx].action = 'confirmed';
  setCardState(card, 'confirmed');
  updateCounters();
}

function rejectConcept(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  conceptsState[idx].action = 'rejected';
  setCardState(card, 'rejected');
  updateCounters();
  showUndoToast(idx);
}

function editConcept(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  setCardState(card, 'editing');
  card.querySelector('.edit-fields').classList.remove('d-none');
  card.querySelector('.display-fields').classList.add('d-none');
}

function saveConcept(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  const nameInput = card.querySelector('.edit-name');
  const descInput = card.querySelector('.edit-description');
  const domainInput = card.querySelector('.concept-domain');
  conceptsState[idx].name = nameInput.value.trim();
  conceptsState[idx].description = descInput.value.trim();
  conceptsState[idx].domain_tag = domainInput.value.trim();
  card.querySelector('.edit-fields').classList.add('d-none');
  card.querySelector('.display-fields').classList.remove('d-none');
  setCardState(card, conceptsState[idx].action);
  renderState();
}

function cancelEdit(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  card.querySelector('.edit-fields').classList.add('d-none');
  card.querySelector('.display-fields').classList.remove('d-none');
  setCardState(card, conceptsState[idx].action);
}

function undoReject(idx) {
  const card = document.querySelector(`.concept-card[data-index="${idx}"]`);
  if (!card) return;
  conceptsState[idx].action = 'pending';
  setCardState(card, 'pending');
  updateCounters();
  hideUndoToast();
}

function addCustomConcept() {
  const idx = conceptsState.length;
  conceptsState.push({ id: idx, name: '', description: '', domain_tag: '', source_excerpt: '', action: 'pending', is_custom: true });
  const container = document.getElementById('conceptCards');
  if (!container) return;
  const card = document.createElement('div');
  card.className = 'concept-card editing';
  card.dataset.index = idx;
  card.innerHTML = `
    <div class="concept-card-overlay d-none"><i class="bi bi-check-circle-fill"></i></div>
    <div class="display-fields d-none">
      <h5 class="concept-name"></h5>
      <p class="concept-description"></p>
      <div class="concept-excerpt small fst-italic text-muted"></div>
      <input type="text" class="form-control concept-domain mt-2" placeholder="Domain tag">
    </div>
    <div class="edit-fields">
      <input type="text" class="form-control mb-2 edit-name" placeholder="Concept name" />
      <textarea class="form-control mb-2 edit-description" rows="3" placeholder="Concept description"></textarea>
      <input type="text" class="form-control concept-domain mb-2" placeholder="Domain tag" />
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-success" type="button" onclick="saveConcept(${idx}); conceptsState[${idx}].action='confirmed';">Save</button>
        <button class="btn btn-sm btn-outline-secondary" type="button" onclick="cancelEdit(${idx})">Cancel</button>
      </div>
    </div>
    <div class="mt-2 d-flex gap-2">
      <button class="btn btn-sm btn-success" type="button" onclick="confirmConcept(${idx});">✓ Confirm</button>
      <button class="btn btn-sm btn-outline-secondary" type="button" onclick="editConcept(${idx});">✎ Edit</button>
      <button class="btn btn-sm btn-danger" type="button" onclick="rejectConcept(${idx});">✕ Reject</button>
    </div>
  `;
  container.appendChild(card);
  updateCounters();
}

function showUndoToast(idx) {
  hideUndoToast();
  const toast = document.createElement('div');
  toast.className = 'undo-toast';
  toast.id = 'undoToast';
  toast.innerHTML = `Concept rejected. <a href="#" class="text-muted text-decoration-underline" onclick="undoReject(${idx});return false;">Undo</a>`;
  document.body.appendChild(toast);
  setTimeout(() => hideUndoToast(), 5000);
}

function hideUndoToast() {
  const toast = document.getElementById('undoToast');
  if (toast) toast.remove();
}

function highlightExcerpt(excerpt) {
  const container = document.getElementById('sourceContent');
  if (!container) return;
  if (!originalSourceHtml) originalSourceHtml = container.innerHTML;
  container.innerHTML = originalSourceHtml;
  if (!excerpt) return;
  const snippet = excerpt.slice(0, 200).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  try {
    const regex = new RegExp(snippet, 'i');
    container.innerHTML = originalSourceHtml.replace(regex, (match) => `<span class="concept-highlight">${match}</span>`);
  } catch (e) {
    // ignore
  }
}

function attachHoverHandlers() {
  document.querySelectorAll('.concept-card').forEach((card) => {
    card.addEventListener('mouseenter', () => {
      const idx = parseInt(card.dataset.index, 10);
      const concept = conceptsState[idx];
      highlightExcerpt(concept ? concept.source_excerpt : '');
    });
    card.addEventListener('mouseleave', () => highlightExcerpt(''));
  });
}

function submitConceptsForm(event) {
  event.preventDefault();
  const form = document.getElementById('conceptForm');
  if (!form) return;
  const input = document.getElementById('conceptsPayload');
  input.value = JSON.stringify(conceptsState);
  form.submit();
}

function initProcessingPolling(itemId) {
  const messages = [
    'Analyzing your content with AI...',
    'Identifying key frameworks and principles...',
    'Finding the most retrievable knowledge units...',
    'Almost ready...'
  ];
  let msgIndex = 0;
  const messageEl = document.getElementById('processingMessage');
  setInterval(() => {
    msgIndex = (msgIndex + 1) % messages.length;
    if (messageEl) messageEl.textContent = messages[msgIndex];
  }, 3000);

  let failures = 0;
  setInterval(() => {
    fetch(`/import/status/${itemId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status === 'completed' || data.status === 'failed') {
          window.location.href = `/import/review/${itemId}`;
        }
      })
      .catch(() => {
        failures += 1;
        if (failures >= 10) {
          const fallback = document.getElementById('processingFallback');
          if (fallback) fallback.classList.remove('d-none');
        }
      });
  }, 2000);
}

window.initConcepts = initConcepts;
window.confirmConcept = confirmConcept;
window.rejectConcept = rejectConcept;
window.editConcept = editConcept;
window.saveConcept = saveConcept;
window.cancelEdit = cancelEdit;
window.addCustomConcept = addCustomConcept;
window.submitConceptsForm = submitConceptsForm;
window.attachHoverHandlers = attachHoverHandlers;
window.initProcessingPolling = initProcessingPolling;
