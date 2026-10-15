'use strict';
(() => {
  // The form always posts to the help endpoint, including on login/course pages.
  document.querySelectorAll('[data-portal-chat]').forEach(chat => {
    const form = chat.querySelector('[data-chat-form]');
    const log = chat.querySelector('[data-chat-log]');
    const input = chat.querySelector('[data-chat-input]');
    const button = chat.querySelector('[data-chat-send]');
    const status = chat.querySelector('[data-chat-status]');
    function line(text, label) {
      const p = document.createElement('p');
      p.className = 'chat-line ' + (label === 'You' ? 'chat-user' : 'chat-assistant');
      const heading = document.createElement('strong');
      heading.textContent = label;
      const content = document.createElement('span');
      content.textContent = text;
      p.append(heading, content);
      log.appendChild(p);
      log.scrollTop = log.scrollHeight;
    }
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!input.value.trim() || button.disabled) return;
      const data = new FormData(form);
      const question = input.value;
      line(question, 'You');
      button.disabled = true;
      input.readOnly = true;
      status.textContent = 'Finding an answer…';
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 20000);
      try {
        const response = await fetch(form.action, {method: 'POST', body: data, signal: controller.signal});
        if (response.status === 429) {
          const result = await response.json();
          line(result.error, 'Assistant');
          status.textContent = 'Please wait before asking another question.';
          return;
        }
        if (!response.ok) throw new Error('Request failed');
        const result = await response.json();
        if (result.answer) line(result.answer, 'Assistant');
        if (result.fallback) line(result.fallback, 'Assistant');
        for (const reply of result.replies) {
          line(reply.text, 'Assistant');
          const link = document.createElement('a');
          // Navigation URLs are supplied by the server's role-specific allowlist.
          link.href = reply.url;
          link.textContent = reply.label + ' →';
          link.className = 'chat-resource-link';
          log.appendChild(link);
        }
        log.scrollTop = log.scrollHeight;
        input.value = '';
        status.textContent = result.mode === 'ai' ? 'AI response · verify important details with your school.' : 'Guided portal help';
      } catch (_) {
        line('I couldn’t connect. Please try again. If your session expired, refresh this page and sign in.', 'Assistant');
        status.textContent = 'Unable to connect · your question is still in the text box.';
      } finally {
        window.clearTimeout(timeout);
        button.disabled = false;
        input.readOnly = false;
        // Do not steal focus if the visitor closed the popup or moved elsewhere.
        if (!chat.closest('[hidden]') && chat.contains(document.activeElement)) input.focus();
      }
    });
    chat.querySelectorAll('[data-topic]').forEach(topic => topic.addEventListener('click', () => {
      if (button.disabled) return;
      input.value = topic.dataset.topic;
      form.requestSubmit();
    }));
  });

  const widget = document.querySelector('[data-assistant-widget]');
  if (!widget) return;
  const launcher = widget.querySelector('[data-chat-toggle]');
  const panel = widget.querySelector('[role=dialog]');
  const close = widget.querySelector('[data-chat-close]');
  const input = widget.querySelector('[data-chat-input]');
  let welcomeTimer;
  const visitKey = 'schoolms-welcome-v1:' + widget.dataset.visitKey;
  function markVisited() {
    try { sessionStorage.setItem(visitKey, 'seen'); } catch (_) { /* Storage is optional. */ }
  }
  function show(manual) {
    if (manual) window.clearTimeout(welcomeTimer);
    panel.hidden = false;
    launcher.setAttribute('aria-expanded', 'true');
    markVisited();
    if (manual) input.focus();
  }
  function hide() {
    window.clearTimeout(welcomeTimer);
    const restoreFocus = panel.contains(document.activeElement);
    panel.hidden = true;
    launcher.setAttribute('aria-expanded', 'false');
    markVisited();
    if (restoreFocus) launcher.focus();
  }
  launcher.addEventListener('click', () => panel.hidden ? show(true) : hide());
  close.addEventListener('click', hide);
  widget.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) { hide(); event.stopPropagation(); }
  });
  let visited = false;
  try { visited = sessionStorage.getItem(visitKey) === 'seen'; } catch (_) { /* First-visit welcome still works. */ }
  if (!visited) welcomeTimer = window.setTimeout(() => show(false), 900);
})();
