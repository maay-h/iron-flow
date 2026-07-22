var otpFlow = null;
var resendTimer = null;

function showLockState(id) {
  ['lock-state', 'setup-state', 'forgot-state'].forEach(function(s) {
    document.getElementById(s).style.display = s === id ? 'flex' : 'none';
  });
  setTimeout(function() {
    var inp = document.querySelector('#' + id + ' input');
    if (inp) inp.focus();
  }, 100);
}

function showError(flow, msg) {
  document.getElementById(flow + '-otp-section').style.display = 'block';
  document.getElementById(flow + '-otp-error').textContent = msg;
}

function sendOTP(flow) {
  otpFlow = flow;
  var btn = document.querySelector('#' + flow + '-state .btn-send');
  btn.disabled = true;
  btn.textContent = 'Sending...';
  document.getElementById(flow + '-otp-error').textContent = '';
  document.getElementById(flow + '-email-section').style.display = 'none';

  fetch('/api/send-otp', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        document.getElementById(flow + '-otp-section').style.display = 'block';
        startResendTimer(flow);
      } else {
        showError(flow, d.error || 'Failed to send OTP');
        document.getElementById(flow + '-email-section').style.display = 'block';
      }
      btn.disabled = false;
      btn.textContent = 'Send OTP';
    })
    .catch(function() {
      btn.disabled = false;
      btn.textContent = 'Send OTP';
      showError(flow, 'Network error');
      document.getElementById(flow + '-email-section').style.display = 'block';
    });
}

function verifyOTP(flow) {
  var code = document.getElementById(flow + '-otp').value.trim();
  if (!code || code.length < 4) {
    document.getElementById(flow + '-otp-error').textContent = 'Enter the 6-digit OTP';
    return;
  }
  var btn = document.querySelector('#' + flow + '-state .btn-verify');
  btn.disabled = true;
  btn.textContent = 'Verifying...';

  fetch('/api/verify-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp: code })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) {
      document.getElementById(flow + '-password-section').style.display = 'block';
      document.getElementById(flow + '-otp-section').style.display = 'none';
    } else {
      document.getElementById(flow + '-otp-error').textContent = d.error || 'Invalid OTP';
    }
    btn.disabled = false;
    btn.textContent = 'Verify';
  })
  .catch(function() {
    document.getElementById(flow + '-otp-error').textContent = 'Network error';
    btn.disabled = false;
    btn.textContent = 'Verify';
  });
}

function savePassword() {
  var pwd = document.getElementById('setup-password').value;
  var confirm = document.getElementById('setup-confirm').value;
  var err = document.getElementById('setup-password-error');
  if (pwd.length < 4) { err.textContent = 'Password must be at least 4 characters'; return; }
  if (pwd !== confirm) { err.textContent = 'Passwords do not match'; return; }
  err.textContent = '';

  fetch('/api/set-password', {
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

function startResendTimer(flow) {
  if (resendTimer) clearInterval(resendTimer);
  var btn = document.getElementById(flow + '-resend');
  var seconds = 30;
  btn.disabled = true;
  btn.textContent = 'Resend in ' + seconds + 's';
  resendTimer = setInterval(function() {
    seconds--;
    if (seconds <= 0) {
      clearInterval(resendTimer);
      resendTimer = null;
      btn.disabled = false;
      btn.textContent = 'Resend OTP';
    } else {
      btn.textContent = 'Resend in ' + seconds + 's';
    }
  }, 1000);
}

function resendOTP(flow) {
  document.getElementById(flow + '-otp').value = '';
  document.getElementById(flow + '-otp-error').textContent = '';
  document.getElementById(flow + '-otp-section').style.display = 'none';
  document.getElementById(flow + '-email-section').style.display = 'block';
  sendOTP(flow);
}

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
  ['setup', 'forgot'].forEach(function(flow) {
    document.getElementById(flow + '-otp')?.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') verifyOTP(flow);
    });
    document.getElementById(flow + '-password')?.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && flow === 'setup') savePassword();
    });
    document.getElementById(flow + '-confirm')?.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && flow === 'setup') savePassword();
    });
    document.getElementById('forgot-password')?.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') saveNewPassword();
    });
    document.getElementById('forgot-confirm')?.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') saveNewPassword();
    });
  });
});
