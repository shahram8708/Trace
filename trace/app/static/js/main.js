function handleNavbarScroll() {
  const nav = document.querySelector('.navbar-trace');
  if (!nav) return;
  if (window.scrollY > 50) {
    nav.classList.add('scrolled');
  } else {
    nav.classList.remove('scrolled');
  }
}

function setupFlashDismiss() {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach((alert) => {
    setTimeout(() => {
      alert.classList.remove('show');
      alert.classList.add('fade');
      setTimeout(() => alert.remove(), 300);
    }, 5000);
  });
}

function setupPasswordStrength() {
  const passwordField = document.getElementById('password');
  if (!passwordField) return;
  let bar = document.querySelector('#password-strength .bar');
  const container = document.getElementById('password-strength');
  if (!bar && container) {
    bar = document.createElement('div');
    bar.className = 'bar';
    container.appendChild(bar);
  }
  const evaluate = (value) => {
    let strength = 0;
    if (value.length >= 8) strength += 1;
    if (/[A-Z]/.test(value)) strength += 1;
    if (/\d/.test(value)) strength += 1;
    let width = ['0%', '33%', '66%', '100%'][strength];
    let color = '#ef4444';
    if (strength === 2) color = '#f59e0b';
    if (strength === 3) color = '#10b981';
    if (bar) {
      bar.style.width = width;
      bar.style.background = color;
    }
  };
  passwordField.addEventListener('input', (e) => evaluate(e.target.value));
  evaluate(passwordField.value || '');
}

function setupPricingToggle() {
  const toggle = document.getElementById('billingToggle');
  const monthly = document.getElementById('plan-monthly');
  const annual = document.getElementById('plan-annual');
  if (!toggle || !monthly || !annual) return;
  const sync = () => {
    const annualMode = toggle.checked;
    annual.classList.toggle('d-none', !annualMode);
    monthly.classList.toggle('d-none', annualMode);
  };
  toggle.addEventListener('change', sync);
  sync();
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

async function initiateRazorpayCheckout(planType) {
  try {
    const response = await fetch('/billing/create-order', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ plan_type: planType }),
    });
    if (!response.ok) throw new Error('Order creation failed');
    const data = await response.json();
    if (!data.subscription_id) throw new Error('Missing subscription');
    const keyId = data.key_id || window.RAZORPAY_KEY_ID || '';
    if (!keyId) throw new Error('Payment key missing');
    const options = {
      key: keyId,
      subscription_id: data.subscription_id,
      currency: 'INR',
      name: 'Trace',
      description: planType === 'annual' ? 'Trace Pro Annual' : 'Trace Pro Monthly',
      // Explicitly enable all Razorpay payment methods
      method: {
        card: true,
        netbanking: true,
        upi: true,
        wallet: true,
        emi: true,
        paylater: true,
      },
      handler: function (res) {
        const payload = { ...res, plan_type: planType };
        fetch('/billing/verify-payment', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(payload),
        })
          .then((resp) => {
            if (resp && resp.ok) {
              window.location = '/billing/success';
            } else {
              window.location = '/billing/failure';
            }
          })
          .catch(() => window.location = '/billing/failure');
      },
      modal: {
        ondismiss: function () {
          console.log('Payment modal closed');
        }
      }
    };
    const rzp = new window.Razorpay(options);
    rzp.open();
  } catch (err) {
    alert('Unable to start checkout right now. Please try again.');
    console.error(err);
  }
}

function setupSidebarToggle() {
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  if (!toggle || !sidebar) return;
  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('d-none');
  });
}

function setupFormLoading() {
  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"], input[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Working...';
      }
    });
  });
}

function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      const success = document.execCommand('copy');
      document.body.removeChild(textarea);
      return success ? resolve() : reject();
    } catch (err) {
      document.body.removeChild(textarea);
      return reject(err);
    }
  });
}

function enhanceMarkdownCopy(block) {
  const codeBlocks = block.querySelectorAll('div.highlight');
  codeBlocks.forEach((wrapper) => {
    wrapper.style.position = 'relative';
    const codeEl = wrapper.querySelector('code');
    if (!codeEl) return;
    const langClass = Array.from(codeEl.classList || []).find((cls) => cls.startsWith('language-'));
    if (langClass) {
      wrapper.dataset.language = langClass.replace('language-', '').toUpperCase();
    }
    if (wrapper.querySelector('.code-copy-btn')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'code-copy-btn';
    btn.textContent = 'Copy';
    btn.setAttribute('aria-label', 'Copy code');
    btn.addEventListener('click', () => {
      const text = codeEl.textContent || '';
      if (!text.trim()) return;
      copyToClipboard(text)
        .then(() => {
          btn.textContent = 'Copied ✓';
          btn.classList.add('copied');
          setTimeout(() => {
            btn.textContent = 'Copy';
            btn.classList.remove('copied');
          }, 2000);
        })
        .catch(() => {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        });
    });
    wrapper.appendChild(btn);
  });
}

function enhanceExternalLinks(block) {
  const anchors = block.querySelectorAll('a[href^="http"]');
  anchors.forEach((a) => {
    try {
      const url = new URL(a.href);
      if (url.hostname && url.hostname !== window.location.hostname) {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
      }
    } catch (err) {
      // ignore malformed URLs
    }
  });
}

function enhanceTocScroll(block) {
  block.querySelectorAll('.markdown-toc a').forEach((anchor) => {
    anchor.addEventListener('click', (event) => {
      const href = anchor.getAttribute('href');
      if (!href || !href.startsWith('#')) return;
      event.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        const offset = target.getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({ top: offset, behavior: 'smooth' });
      }
    });
  });
}

function showAnchorTooltip(anchor) {
  const tooltip = document.createElement('span');
  tooltip.className = 'anchor-copy-toast';
  tooltip.textContent = 'Link copied!';
  anchor.appendChild(tooltip);
  setTimeout(() => tooltip.remove(), 1200);
}

function enhanceHeadingAnchors(block) {
  block.querySelectorAll('.heading-anchor').forEach((anchor) => {
    anchor.addEventListener('click', (event) => {
      event.preventDefault();
      const href = anchor.getAttribute('href') || '';
      const fullUrl = `${window.location.origin}${window.location.pathname}${href}`;
      copyToClipboard(fullUrl)
        .then(() => showAnchorTooltip(anchor))
        .catch(() => showAnchorTooltip(anchor));
    });
  });
}

function enhanceImages(block) {
  block.querySelectorAll('img').forEach((img) => {
    if (!img.getAttribute('loading')) {
      img.setAttribute('loading', 'lazy');
    }
    if (!img.getAttribute('decoding')) {
      img.setAttribute('decoding', 'async');
    }
    img.addEventListener('error', () => {
      const placeholder = document.createElement('div');
      placeholder.className = 'markdown-image-placeholder';
      placeholder.textContent = img.getAttribute('alt') || 'Image unavailable';
      img.replaceWith(placeholder);
    }, { once: true });
  });
}

function enhanceTables(block) {
  block.querySelectorAll('table').forEach((table) => {
    const parent = table.parentElement;
    const needsWrap = !parent.classList || !parent.classList.contains('table-responsive');
    if (needsWrap) {
      const wrapper = document.createElement('div');
      wrapper.className = 'table-responsive';
      wrapper.setAttribute('role', 'region');
      wrapper.setAttribute('aria-label', 'Data table');
      parent.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });
}

function enhanceMarkdownBlocks() {
  const markdownBlocks = document.querySelectorAll('[data-markdown-rendered="true"]');
  markdownBlocks.forEach((block) => {
    enhanceMarkdownCopy(block);
    enhanceExternalLinks(block);
    enhanceTocScroll(block);
    enhanceHeadingAnchors(block);
    enhanceImages(block);
    enhanceTables(block);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  handleNavbarScroll();
  setupFlashDismiss();
  setupPasswordStrength();
  setupPricingToggle();
  setupSidebarToggle();
  setupFormLoading();
   enhanceMarkdownBlocks();
});
window.addEventListener('scroll', handleNavbarScroll);

// Expose helpers
window.getCsrfToken = getCsrfToken;
window.initiateRazorpayCheckout = initiateRazorpayCheckout;
