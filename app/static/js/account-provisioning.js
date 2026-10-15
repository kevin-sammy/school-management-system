'use strict';
(() => {
  let controller, timer, sequence = 0;
  async function preview(url, first, last, output, status) {
    window.clearTimeout(timer);
    if (controller) controller.abort();
    const current = ++sequence;
    if (!first.trim() || !last.trim()) {
      output.value = '';
      if (status) status.textContent = 'Enter both names to generate the username.';
      return;
    }
    if (status) status.textContent = 'Checking the available username…';
    timer = window.setTimeout(async () => {
      controller = new AbortController();
      try {
        const target = new URL(url, location.origin);
        target.searchParams.set('first_name', first.trim());
        target.searchParams.set('last_name', last.trim());
        const response = await fetch(target, {signal: controller.signal});
        if (!response.ok) throw new Error('Preview unavailable');
        const result = await response.json();
        if (current !== sequence) return;
        output.value = result.username;
        if (status) status.textContent = 'First initial + last name. The final available username is confirmed when saved.';
      } catch (error) {
        if (error.name === 'AbortError' || current !== sequence) return;
        output.value = '';
        if (status) status.textContent = 'Preview unavailable. The server will generate the username when you save.';
      }
    }, 250);
  }
  const form = document.querySelector('[data-profile-account]');
  if (form) {
    const first = form.querySelector('[name=first_name]');
    const last = form.querySelector('[name=last_name]');
    const role = form.querySelector('[name=role]');
    const state = form.querySelector('[name=status]');
    const panel = form.querySelector('[data-profile-login]');
    const output = form.querySelector('[data-profile-username]');
    const status = form.querySelector('[data-profile-status]');
    const password = form.querySelector('[data-profile-password]');
    const email = form.querySelector('[name=email]');
    const confirmation = form.querySelector('[data-password-confirm]');
    function update() {
      const teacher = form.dataset.accountKind === 'parent' || role.value.toLowerCase() === 'teacher';
      const active = !state || state.value === 'active';
      panel.hidden = !teacher;
      if (password) { password.required = teacher && active && !form.dataset.linkedUsername; password.disabled = !teacher || !active; }
      if (confirmation && password) { confirmation.disabled = !teacher || !active; confirmation.required = teacher && active && password.value.length > 0; }
      email.required = teacher && active && !form.dataset.linkedUsername;
      if (!teacher) { ++sequence; window.clearTimeout(timer); if (controller) controller.abort(); return; }
      if (form.dataset.linkedUsername) { output.value = form.dataset.linkedUsername; return; }
      preview(form.dataset.previewUrl, first.value, last.value, output, status);
    }
    first.addEventListener('input', update);
    last.addEventListener('input', update);
    if (confirmation && password) {
      password.addEventListener('input', () => { confirmation.required = password.value.length > 0; });
    }
    if (role) role.addEventListener('change', update);
    if (state) state.addEventListener('change', update);
    update();
  }
  const role = document.getElementById('account-role');
  const profiles = document.getElementById('account-profile');
  const username = document.getElementById('portal-username');
  if (role && profiles && username) {
    function update() {
      const teacher = ['teacher', 'parent'].includes(role.value);
      username.readOnly = teacher;
      username.required = !teacher;
      if (!teacher) { ++sequence; window.clearTimeout(timer); if (controller) controller.abort(); username.value = ''; return; }
      const option = profiles.selectedOptions[0];
      if (option) preview(role.dataset.previewUrl, option.dataset.firstName || '', option.dataset.lastName || '', username);
    }
    role.addEventListener('change', update);
    profiles.addEventListener('change', update);
    update();
  }
})();
