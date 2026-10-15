'use strict';
const form = document.getElementById('exam-form');
const deadline = Date.parse(form.dataset.deadline);
const token = form.querySelector('[name=csrf_token]').value;
const status = document.getElementById('save-status');
let saving = false, finishing = false;
async function save() {
  if (saving || finishing) return;
  saving = true;
  const data = new FormData(form);
  data.set('action', 'save');
  try {
    const response = await fetch(location.pathname, {method:'POST', body:data});
    const result = await response.json();
    if (result.finished) { location.reload(); return; }
    if (!response.ok) throw new Error('Save failed');
    status.textContent = 'Answers saved at ' + new Date().toLocaleTimeString();
  } catch (_) { status.textContent = 'Save failed. Check your connection; keep this page open.'; }
  finally { saving = false; }
}
setInterval(save, 15000);
form.addEventListener('change', save);
form.addEventListener('submit', () => { finishing = true; });
function tick() {
  const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
  document.getElementById('exam-clock').textContent = 'Time remaining: ' + Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2,'0');
  if (seconds === 0 && !finishing) { finishing = true; form.requestSubmit(document.getElementById('exam-submit')); }
}
setInterval(tick, 1000); tick();
async function record(kind) {
  if (finishing) return;
  const data = new FormData(); data.set('csrf_token',token); data.set('kind',kind);
  try { await fetch(form.dataset.eventsUrl, {method:'POST', body:data, keepalive:true}); } catch (_) { /* Human review never assumes complete logs. */ }
}
document.addEventListener('visibilitychange', () => { if (document.hidden) record('visibility_hidden'); });
window.addEventListener('blur', () => record('focus_lost'));
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) record('fullscreen_exit'); });
form.addEventListener('paste', () => record('paste_attempt'));
document.getElementById('fullscreen').addEventListener('click', async () => {
  try { await document.documentElement.requestFullscreen(); }
  catch (_) { status.textContent = 'Fullscreen unavailable. You can continue; tell your teacher if needed.'; }
});
