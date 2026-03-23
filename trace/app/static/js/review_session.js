(() => {
  const sessionDataEl = document.getElementById('session-data');
  if (!sessionDataEl) return;

  const SESSION_DATA = JSON.parse(sessionDataEl.textContent);
  const concepts = SESSION_DATA.concepts || [];
  const sessionId = SESSION_DATA.session_id;
  const totalCount = SESSION_DATA.total_count || concepts.length;
  const storageKey = `trace_session_${sessionId}`;

  let currentIndex = 0;
  let qualityRatingsSummary = { 0: 0, 1: 0, 3: 0, 5: 0 };
  let isComplete = false;
  let cachedResponseText = '';

  const els = {
    progressText: document.getElementById('progress-text'),
    progressBar: document.getElementById('progress-bar'),
    domainBadge: document.getElementById('domain-badge'),
    conceptTitle: document.getElementById('concept-title'),
    sourceLabel: document.getElementById('source-label'),
    promptSection: document.getElementById('prompt-section'),
    revealSection: document.getElementById('reveal-section'),
    textarea: document.getElementById('response-text'),
    charCounter: document.getElementById('char-counter'),
    checkBtn: document.getElementById('check-btn'),
    yourRecall: document.getElementById('your-recall'),
    conceptAnswer: document.getElementById('concept-answer'),
    sourceExcerpt: document.getElementById('source-excerpt'),
    ratingButtons: document.querySelectorAll('[data-quality]'),
    errorBox: document.getElementById('rating-error'),
    completeView: document.getElementById('session-complete'),
    sessionBody: document.getElementById('session-body'),
    qualityTotals: {
      again: document.getElementById('again-count'),
      hard: document.getElementById('hard-count'),
      good: document.getElementById('good-count'),
      easy: document.getElementById('easy-count'),
    },
    streakValue: document.getElementById('complete-streak'),
    streakRecord: document.getElementById('complete-record'),
    completionChart: document.getElementById('quality-doughnut'),
    resumeBanner: document.getElementById('resume-banner'),
    resumeBtn: document.getElementById('resume-btn'),
    restartBtn: document.getElementById('restart-btn'),
  };

  function saveProgress() {
    const payload = { currentIndex, qualityRatingsSummary };
    sessionStorage.setItem(storageKey, JSON.stringify(payload));
  }

  function clearProgress() {
    sessionStorage.removeItem(storageKey);
  }

  function restoreProgress() {
    const raw = sessionStorage.getItem(storageKey);
    if (!raw) return false;
    try {
      const parsed = JSON.parse(raw);
      if (parsed.currentIndex && parsed.currentIndex < concepts.length) {
        currentIndex = parsed.currentIndex;
        qualityRatingsSummary = parsed.qualityRatingsSummary || qualityRatingsSummary;
        return true;
      }
    } catch (e) {
      console.warn('Unable to restore session progress');
    }
    return false;
  }

  function updateProgressUI() {
    if (!els.progressText || !els.progressBar) return;
    const position = Math.min(currentIndex + 1, totalCount);
    els.progressText.textContent = `Concept ${position} of ${totalCount}`;
    const pct = Math.round((position / totalCount) * 100);
    els.progressBar.style.width = `${pct}%`;
    els.progressBar.setAttribute('aria-valuenow', pct);
  }

  function applyDomainBadge(domain) {
    if (!els.domainBadge) return;
    const slug = (domain || 'general').toLowerCase().replace(/\s+/g, '-');
    els.domainBadge.className = 'domain-pill domain-' + slug;
    els.domainBadge.textContent = domain;
  }

  function renderConcept(index) {
    const concept = concepts[index];
    if (!concept) return;

    els.promptSection.classList.remove('transition-out');
    els.promptSection.classList.add('transition-in');
    els.revealSection.classList.add('d-none');
    els.promptSection.classList.remove('d-none');

    applyDomainBadge(concept.domain_tag || 'General');
    els.conceptTitle.textContent = concept.name;
    els.sourceLabel.textContent = concept.source_title ? `From: ${concept.source_title}` : 'From your knowledge library';
    els.textarea.value = '';
    els.charCounter.textContent = '0 characters';
    els.checkBtn.disabled = true;
    cachedResponseText = '';
    setButtonsDisabled(false);
    hideError();
    updateProgressUI();
    saveProgress();
  }

  function revealConcept(index) {
    const concept = concepts[index];
    cachedResponseText = els.textarea.value.trim();
    els.yourRecall.textContent = cachedResponseText;
    els.conceptAnswer.textContent = concept.description;
    if (concept.source_excerpt) {
      els.sourceExcerpt.textContent = concept.source_excerpt;
      els.sourceExcerpt.parentElement.classList.remove('d-none');
    } else {
      els.sourceExcerpt.parentElement.classList.add('d-none');
    }
    els.promptSection.classList.add('transition-out');
    setTimeout(() => {
      els.promptSection.classList.add('d-none');
      els.revealSection.classList.remove('d-none');
      els.revealSection.classList.add('transition-in');
    }, 200);
  }

  function setButtonsDisabled(state) {
    els.ratingButtons.forEach((btn) => {
      btn.disabled = state;
    });
  }

  function showError(message) {
    if (!els.errorBox) return;
    els.errorBox.classList.remove('d-none');
    els.errorBox.textContent = message;
  }

  function hideError() {
    if (els.errorBox) {
      els.errorBox.classList.add('d-none');
      els.errorBox.textContent = '';
    }
  }

  async function submitRating(quality) {
    setButtonsDisabled(true);
    hideError();
    const payload = {
      concept_id: concepts[currentIndex].id,
      session_id: sessionId,
      quality_rating: quality,
      user_response_text: cachedResponseText,
    };
    try {
      const response = await fetch('/review/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (window.getCsrfToken && window.getCsrfToken()) || '',
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        showError('Something went wrong saving your review. Please try again.');
        setButtonsDisabled(false);
        return;
      }
      qualityRatingsSummary[quality] = (qualityRatingsSummary[quality] || 0) + 1;
      advanceToNext();
      saveProgress();
    } catch (err) {
      console.error(err);
      showError('Network error. Please try again.');
      setButtonsDisabled(false);
    }
  }

  function animateTransition(nextFn) {
    els.sessionBody.classList.add('transition-out');
    setTimeout(() => {
      nextFn();
      els.sessionBody.classList.remove('transition-out');
      els.sessionBody.classList.add('transition-in');
      setTimeout(() => els.sessionBody.classList.remove('transition-in'), 250);
    }, 200);
  }

  function advanceToNext() {
    currentIndex += 1;
    if (currentIndex < concepts.length) {
      animateTransition(() => renderConcept(currentIndex));
    } else {
      completeSession();
    }
  }

  async function completeSession() {
    if (isComplete) return;
    isComplete = true;
    window.removeEventListener('beforeunload', beforeUnloadHandler);
    try {
      const response = await fetch('/review/session/end', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (window.getCsrfToken && window.getCsrfToken()) || '',
        },
        body: JSON.stringify({ session_id: sessionId, total_reviewed: concepts.length }),
      });
      if (response.ok) {
        const data = await response.json();
        renderCompletion(data.summary || {}, data.streak, data.longest_streak, data.is_new_streak_record);
      } else {
        renderCompletion({}, concepts.length, null, false);
      }
    } catch (err) {
      console.error(err);
      renderCompletion({}, concepts.length, null, false);
    }
    clearProgress();
  }

  function renderCompletion(summary = {}, streak = null, longest = null, isRecord = false) {
    if (els.sessionBody) els.sessionBody.classList.add('d-none');
    if (els.completeView) els.completeView.classList.add('active');
    els.qualityTotals.again.textContent = summary.again_count ?? qualityRatingsSummary[0] ?? 0;
    els.qualityTotals.hard.textContent = summary.hard_count ?? qualityRatingsSummary[1] ?? 0;
    els.qualityTotals.good.textContent = summary.good_count ?? qualityRatingsSummary[3] ?? 0;
    els.qualityTotals.easy.textContent = summary.easy_count ?? qualityRatingsSummary[5] ?? 0;
    if (els.streakValue && streak !== null) els.streakValue.textContent = `${streak} day streak`;
    if (els.streakRecord && isRecord) {
      els.streakRecord.classList.remove('d-none');
    }
    const chartData = {
      again_count: summary.again_count ?? qualityRatingsSummary[0] ?? 0,
      hard_count: summary.hard_count ?? qualityRatingsSummary[1] ?? 0,
      good_count: summary.good_count ?? qualityRatingsSummary[3] ?? 0,
      easy_count: summary.easy_count ?? qualityRatingsSummary[5] ?? 0,
    };
    if (window.renderQualityDoughnutChart && els.completionChart) {
      window.renderQualityDoughnutChart('quality-doughnut', chartData);
    }
  }

  function beforeUnloadHandler(e) {
    if (isComplete) return;
    if (currentIndex > 0 && currentIndex < concepts.length) {
      e.preventDefault();
      e.returnValue = '';
    }
  }

  function bindEvents() {
    if (els.textarea) {
      els.textarea.addEventListener('input', (e) => {
        const val = e.target.value;
        const len = val.length;
        cachedResponseText = val;
        if (els.charCounter) {
          els.charCounter.textContent = `${len} characters`;
        }
        if (els.checkBtn) {
          els.checkBtn.disabled = len < 20;
        }
      });
    }
    if (els.checkBtn) {
      els.checkBtn.addEventListener('click', () => revealConcept(currentIndex));
    }
    els.ratingButtons.forEach((btn) => {
      btn.addEventListener('click', () => submitRating(parseInt(btn.dataset.quality, 10)));
    });
    const endBtn = document.getElementById('end-session');
    if (endBtn) {
      endBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const confirmEnd = window.confirm('End session early? Your progress so far has been saved.');
        if (confirmEnd) completeSession();
      });
    }
    if (els.resumeBtn && els.resumeBanner) {
      els.resumeBtn.addEventListener('click', () => {
        els.resumeBanner.classList.add('d-none');
        renderConcept(currentIndex);
      });
    }
    if (els.restartBtn && els.resumeBanner) {
      els.restartBtn.addEventListener('click', () => {
        els.resumeBanner.classList.add('d-none');
        currentIndex = 0;
        qualityRatingsSummary = { 0: 0, 1: 0, 3: 0, 5: 0 };
        clearProgress();
        renderConcept(0);
      });
    }
  }

  function init() {
    const hasSaved = restoreProgress();
    if (hasSaved && els.resumeBanner) {
      els.resumeBanner.classList.remove('d-none');
    } else {
      renderConcept(currentIndex);
    }
    bindEvents();
    updateProgressUI();
    window.addEventListener('beforeunload', beforeUnloadHandler);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
