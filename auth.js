function qs(id) { return document.getElementById(id); }

async function login() {
  const username = qs('username').value.trim();
  const password = qs('password').value;
  const msg = qs('msg');
  msg.textContent = '';
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  const data = await res.json();
  if (!data.ok) {
    msg.textContent = data.error || '登录失败';
    return;
  }
  location.href = '/';
}

async function registerUser() {
  const username = qs('username').value.trim();
  const password = qs('password').value;
  const invite_code = qs('inviteCode').value.trim();
  const msg = qs('msg');
  msg.textContent = '';
  const res = await fetch('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, invite_code })
  });
  const data = await res.json();
  if (!data.ok) {
    msg.textContent = data.error || '注册失败';
    return;
  }
  msg.textContent = '注册成功，跳转登录页...';
  setTimeout(() => { location.href = '/login'; }, 900);
}

if (qs('loginBtn')) qs('loginBtn').addEventListener('click', login);
if (qs('registerBtn')) qs('registerBtn').addEventListener('click', registerUser);
