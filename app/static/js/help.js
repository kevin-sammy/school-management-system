'use strict';
const form = document.getElementById('chat-form');
const log = document.getElementById('chat-log');
const input = document.getElementById('chat-message');
const button = document.getElementById('chat-send');
const status = document.getElementById('chat-status');
function line(text, label) {
  const p = document.createElement('p');
  p.textContent = label + ': ' + text;
  log.appendChild(p);
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!input.value.trim() || button.disabled) return;
  const data = new FormData(form);
  line(input.value, 'You');
  button.disabled = true;
  status.textContent = 'Finding an answer…';
  try {
    const response = await fetch(location.pathname, {method: 'POST', body: data});
    const result = await response.json();
    if (response.status === 429) { line(result.error, 'Assistant'); return; }
    if (!response.ok) throw new Error('Request failed');
    if (result.answer) line(result.answer, 'Assistant');
    if (result.fallback) line(result.fallback, 'Assistant');
    for (const reply of result.replies) {
      line(reply.text, 'Assistant');
      const link = document.createElement('a');
      link.href = reply.url;
      link.textContent = reply.label;
      log.appendChild(link);
    }
    input.value = '';
    status.textContent = result.mode === 'ai' ? 'AI response · verify important details with your school.' : 'Guided portal help';
  } catch (_) {
    line('The assistant is unavailable. Try again or use the navigation menu.', 'Assistant');
    status.textContent = 'Unable to connect';
  } finally {
    button.disabled = false;
    input.focus();
  }
});
document.querySelectorAll('[data-topic]').forEach(button => button.addEventListener('click', () => {
  input.value = button.dataset.topic;
  form.requestSubmit();
}));
