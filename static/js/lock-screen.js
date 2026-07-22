function showLockState(id) {
  ['lock-state', 'setup-state', 'forgot-state'].forEach(function(s) {
    document.getElementById(s).style.display = s === id ? 'flex' : 'none';
  });
  setTimeout(function() {
    var inp = document.querySelector('#' + id + ' input');
    if (inp) inp.focus();
  }, 100);
}

function savePassword() {
  var pwd = document.getElementById('setup-password').value;
  var confirm = document.getElementById('setup-confirm').value;
  var err = document.getElementById('setup-password-error');
  if (pwd.length < 4) { err.textContent = 'Password must be at least 4 characters'; return; }
  if (pwd !== confirm) { err.textContent = 'Passwords do not match'; return; }
  err.textContent = '';

  fetch('/api/set-password-direct', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) window.location.reload();
    else err.textContent = d.error || 'Failed to set password';
  });
}

function unlock() {
  var pwd = document.getElementById('login-password').value;
  var err = document.getElementById('login-error');
  if (!pwd) { err.textContent = 'Enter your password'; return; }
  err.textContent = '';

  fetch('/api/verify-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) window.location.reload();
    else err.textContent = 'Wrong password';
  });
}

function saveNewPassword() {
  var pwd = document.getElementById('forgot-password').value;
  var confirm = document.getElementById('forgot-confirm').value;
  var err = document.getElementById('forgot-password-error');
  if (pwd.length < 4) { err.textContent = 'Password must be at least 4 characters'; return; }
  if (pwd !== confirm) { err.textContent = 'Passwords do not match'; return; }
  err.textContent = '';

  fetch('/api/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pwd })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) {
      showLockState('lock-state');
      document.getElementById('login-error').textContent = 'Password reset successfully';
    } else err.textContent = d.error || 'Failed to reset password';
  });
}

function showForgotPassword() { showLockState('forgot-state'); }

function logout() {
  fetch('/api/logout', { method: 'POST' }).then(function() { window.location.reload(); });
}

document.addEventListener('DOMContentLoaded', function() {
  var ls = document.getElementById('lockscreen');
  if (!ls) return;

  fetch('/api/check-setup')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.setup) showLockState('setup-state');
    });

  document.getElementById('login-password')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') unlock();
  });
  document.getElementById('setup-password')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') savePassword();
  });
  document.getElementById('setup-confirm')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') savePassword();
  });
  document.getElementById('forgot-password')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') saveNewPassword();
  });
  document.getElementById('forgot-confirm')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') saveNewPassword();
  });
});
