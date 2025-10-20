(function(){
  // Shared SAR banner behavior (English only, draggable)
  const bannerKey = 'sar_test_banner_dismissed_v1';
  const langKey = 'preferredLanguage';

  function playBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = 'sine'; o.frequency.value = 880; g.gain.value = 0.02;
      o.connect(g); g.connect(ctx.destination); o.start();
      setTimeout(() => { o.stop(); try{ctx.close();}catch(e){} }, 150);
    } catch (e) { /* ignore */ }
  }

  function makeDraggable(el) {
    if (!el || !window.PointerEvent) return;
    let dragging = false, startX=0, startY=0, origX=0, origY=0;
    el.style.touchAction = el.style.touchAction || 'none';
    el.addEventListener('pointerdown', (ev) => {
      dragging = true; try{ el.setPointerCapture(ev.pointerId); }catch(e){}
      startX = ev.clientX; startY = ev.clientY;
      const rect = el.getBoundingClientRect(); origX = rect.left; origY = rect.top;
      el.style.cursor = 'grabbing';
    });
    window.addEventListener('pointermove', (ev) => {
      if (!dragging) return;
      const dx = ev.clientX - startX; const dy = ev.clientY - startY;
      const newLeft = Math.max(8, origX + dx);
      const newTop = Math.max(8, origY + dy);
      el.style.left = newLeft + 'px';
      el.style.top = newTop + 'px';
      el.style.right = 'auto'; el.style.transform = 'none';
      // Persist position for next visit
      try { localStorage.setItem('sar_banner_pos_v1', JSON.stringify({left: newLeft, top: newTop})); } catch(e){}
    });
    window.addEventListener('pointerup', (ev) => {
      if (!dragging) return; dragging = false;
      try{ el.releasePointerCapture(ev.pointerId); }catch(e){}
      el.style.cursor = 'grab';
    });
  }

  function initBanner() {
  const dismissed = localStorage.getItem(bannerKey);
    // Don't default to 'el' here — treat absence of a saved preference as "no preference"
    const lang = localStorage.getItem(langKey);
    const banner = document.getElementById('sar-test-banner');
    const cta = document.getElementById('sar-test-cta');
    const closeBtn = document.getElementById('sar-test-close');
    const langButtons = document.querySelectorAll('.lang-btn');
    const isHome = (window.location.pathname === '/' || window.location.pathname === '' || window.location.pathname.endsWith('index.html'));
    const langToggle = document.querySelector('.language-toggle');
    const headerBannerWrap = document.querySelector('.header-banner-wrap');

    if (!banner) return;

    // Only initialize and show the banner on the site's index page (root or index.html).
    // On other pages we hide the banner and skip draggable/placement logic.
    const isIndex = (window.location.pathname === '/' || window.location.pathname === '' || window.location.pathname.endsWith('index.html'));
    if (!isIndex) {
      // Ensure the banner stays hidden on non-index pages
      try { banner.style.display = 'none'; } catch(e){}
      return;
    }

    // Apply persisted position if present
    let persistedPos = null;
    try {
      persistedPos = JSON.parse(localStorage.getItem('sar_banner_pos_v1') || 'null');
      if (persistedPos && typeof persistedPos.left === 'number' && typeof persistedPos.top === 'number') {
        banner.style.left = persistedPos.left + 'px';
        banner.style.top = persistedPos.top + 'px';
        banner.style.right = 'auto';
        banner.style.transform = 'none';
      }
    } catch(e){ persistedPos = null; }

    // Helper: position banner centered above (or overlapping) the language toggle on index page
    function positionOverToggle() {
      try {
        if (!langToggle) return;
        // Ensure banner is visible so measurements work
        banner.style.display = 'flex';
        banner.style.position = 'fixed';
        banner.style.transform = 'none';
        banner.style.right = 'auto';
        // Small timeout to allow layout; if banner is already displayed this will be near-instant
        setTimeout(() => {
          try {
            const gap = 8; // gap between toggle and banner
            const toggleRect = langToggle.getBoundingClientRect();
            const bRect = banner.getBoundingClientRect();
            const viewportW = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
            const viewportH = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

            // Try to place to the right of the toggle if there is enough horizontal space
            const spaceRight = viewportW - toggleRect.right;
            if (spaceRight >= bRect.width + gap) {
              const left = Math.round(toggleRect.right + gap);
              // Vertically center relative to toggle (clamped)
              let top = Math.round(toggleRect.top + (toggleRect.height / 2) - (bRect.height / 2));
              top = Math.max(gap, Math.min(top, viewportH - bRect.height - gap));
              banner.style.left = left + 'px';
              banner.style.top = top + 'px';
              banner.style.right = 'auto';
              return;
            }

            // If not enough right space, fall back to above if possible, otherwise below
            const preferredAbove = Math.round(toggleRect.top - bRect.height - gap);
            if (preferredAbove >= gap) {
              const left = Math.round(toggleRect.left + (toggleRect.width / 2) - (bRect.width / 2));
              const clampedLeft = Math.max(gap, Math.min(left, viewportW - bRect.width - gap));
              banner.style.left = clampedLeft + 'px';
              banner.style.top = preferredAbove + 'px';
              banner.style.right = 'auto';
              return;
            }

            // Otherwise place below
            const belowTop = Math.round(toggleRect.bottom + gap);
            const left = Math.round(toggleRect.left + (toggleRect.width / 2) - (bRect.width / 2));
            const clampedLeft = Math.max(gap, Math.min(left, viewportW - bRect.width - gap));
            banner.style.left = clampedLeft + 'px';
            banner.style.top = Math.min(belowTop, viewportH - bRect.height - gap) + 'px';
            banner.style.right = 'auto';

            // Do NOT persist this auto-placement; only persist when user drags the banner
          } catch(e){}
        }, 10);
      } catch(e){}
    }

  // Show the banner on index page when not dismissed: fixed top-left by default
  if (!dismissed && isIndex) {
      try {
        // Prefer a header-contained placement if the page provides a headerBannerWrap, otherwise fixed top-left
        if (headerBannerWrap) {
          // Let the header wrapper handle placement (CSS) but ensure it's visible
          banner.style.position = 'absolute';
          banner.style.display = 'flex';
          // If it would overflow the header, fall back to fixed top-left
          try {
            const wrapRect = headerBannerWrap.getBoundingClientRect();
            const bRect = banner.getBoundingClientRect();
            if (bRect.width > wrapRect.width - 12) {
              banner.style.position = 'fixed';
              banner.style.left = '8px';
              banner.style.top = '8px';
              banner.style.right = 'auto';
            }
          } catch (e) {}
        } else {
          banner.style.position = 'fixed';
          banner.style.left = '8px';
          banner.style.top = '8px';
          banner.style.right = 'auto';
          banner.style.display = 'flex';
        }
        playBeep();
        // Make draggable only on index
        makeDraggable(banner);
      } catch (e) { /* ignore */ }
    }

    if (cta) {
      cta.addEventListener('click', function() {
        try { localStorage.setItem(bannerKey, '1'); } catch (e) {}
        window.location.href = '/technology#test-sar-section';
        if (banner) banner.style.display = 'none';
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function() {
        try { localStorage.setItem(bannerKey, '1'); } catch (e) {}
        if (banner) banner.style.display = 'none';
      });
    }

    // Language selection is handled by the page (index.html) via its own switchLanguage() function.
    // Removing language mutation here avoids conflicts with page-level logic and ensures consistent behavior.
  }

  // Wait for DOMContentLoaded to ensure banner exists
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBanner);
  } else {
    initBanner();
  }
})();

