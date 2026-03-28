let state = { sources: [], logs: [], news: [] };
let me = null;
let users = [];
let inviteCodes = [];

const views = {
  news: document.getElementById('view-news'),
  sources: document.getElementById('view-sources'),
  logs: document.getElementById('view-logs'),
  rules: document.getElementById('view-rules'),
  favorites: document.getElementById('view-favorites'),
  admin: document.getElementById('view-admin')
};

function switchView(name) {
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.toggle('active', btn.dataset.view === name));
  Object.entries(views).forEach(([k, el]) => el.classList.toggle('active', k === name));
  document.getElementById('pageTitle').textContent = {
    news: '热点资讯', sources: '监听源', logs: '源头获取记录', rules: '筛选策略（占位）', favorites: '收藏', admin: '平台管理'
  }[name];
}

function safe(s) { return (s ?? '').toString(); }

function renderNews() {
  views.news.innerHTML = `
    <div class="card">
      <div class="card-title">资讯流（真实抓取入库）</div>
      <div class="news-list">
        ${state.news.length ? state.news.map(n => `
          <div class="news-item">
            <h4><a href="${safe(n.url)}" target="_blank" rel="noreferrer" style="color:#dce6ff;text-decoration:none">${safe(n.title)}</a></h4>
            <div class="small">${safe(n.summary)}</div>
            <div class="news-meta"><span>来源: ${safe(n.source)}</span><span>发布时间: ${safe(n.published_at)}</span><span>入库: ${safe(n.created_at)}</span></div>
          </div>
        `).join('') : '<div class="small">暂无数据，点右上角“模拟抓取一批”进行真实抓取。</div>'}
      </div>
    </div>`;
}

function renderSources() {
  views.sources.innerHTML = `
    <div class="card table-wrap">
      <div class="card-title">监听源状态（后端实时）</div>
      <table>
        <thead><tr><th>名称</th><th>类型</th><th>启用</th><th>状态</th><th>最近执行</th></tr></thead>
        <tbody>
          ${state.sources.map(s => `
            <tr>
              <td>${safe(s.name)}</td>
              <td>${safe(s.type)}</td>
              <td>${s.enabled ? 'ON' : 'OFF'}</td>
              <td><span class="badge ${s.last_status === 'ok' ? 'ok' : (s.last_status === 'err' ? 'err' : 'warn')}">${safe(s.last_status)}</span></td>
              <td>${safe(s.last_run_at || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderLogs() {
  views.logs.innerHTML = `
    <div class="card table-wrap">
      <div class="card-title">源头获取记录（可追溯）</div>
      <table>
        <thead><tr><th>时间</th><th>来源</th><th>动作</th><th>结果</th><th>Code</th><th>摘要</th></tr></thead>
        <tbody>
          ${state.logs.map(l => `
            <tr>
              <td>${safe(l.created_at)}</td>
              <td>${safe(l.source)}</td>
              <td>${safe(l.action)}</td>
              <td>${safe(l.result)}</td>
              <td>${safe(l.code)}</td>
              <td>${safe(l.summary)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderRules() {
  views.rules.innerHTML = `<div class="card"><div class="card-title">说明</div><div class="news-list"><div class="small">本版已切到真实抓取，筛选策略先保留占位。下一步可加数据库规则引擎。</div></div></div>`;
}

function renderFavorites() {
  views.favorites.innerHTML = `<div class="card"><div class="card-title">说明</div><div class="news-list"><div class="small">本版以“真实抓取+记录可追溯”为主，收藏将在下一版接入数据库字段编辑。</div></div></div>`;
}

function renderAdmin() {
  if (!me || me.role !== 'admin') {
    views.admin.innerHTML = `<div class="card"><div class="card-title">平台管理</div><div class="news-list"><div class="small">仅管理员可查看。</div></div></div>`;
    return;
  }
  views.admin.innerHTML = `
    <div class="card table-wrap">
      <div class="card-title">用户管理</div>
      <table>
        <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>邀请码</th><th>创建时间</th></tr></thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>${u.id}</td>
              <td>${safe(u.username)}</td>
              <td>${safe(u.role)}</td>
              <td>${safe(u.invite_code_used || '-')}</td>
              <td>${safe(u.created_at)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <div class="card table-wrap">
      <div class="card-title">邀请码列表（注册时需填写）</div>
      <table>
        <thead><tr><th>ID</th><th>邀请码</th><th>状态</th><th>创建时间</th></tr></thead>
        <tbody>
          ${inviteCodes.map(c => `
            <tr>
              <td>${c.id}</td>
              <td>${safe(c.code)}</td>
              <td>${c.enabled ? '启用' : '禁用'}</td>
              <td>${safe(c.created_at)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderAll() {
  renderNews(); renderSources(); renderLogs(); renderRules(); renderFavorites(); renderAdmin();
}

async function loadState() {
  const res = await fetch('/api/state');
  if (res.status === 401) {
    location.href = '/login';
    return;
  }
  state = await res.json();
  renderAll();
}

async function loadMe() {
  const res = await fetch('/api/me');
  if (res.status === 401) {
    location.href = '/login';
    return false;
  }
  const data = await res.json();
  me = data.user;
  document.getElementById('userInfo').textContent = `当前用户：${me.username}（${me.role}）`;
  return true;
}

async function loadAdminData() {
  if (!me || me.role !== 'admin') return;
  const [uRes, cRes] = await Promise.all([
    fetch('/api/admin/users'),
    fetch('/api/admin/invite-codes')
  ]);
  const uData = await uRes.json();
  const cData = await cRes.json();
  users = uData.users || [];
  inviteCodes = cData.invite_codes || [];
}

async function collect() {
  const query = prompt('输入抓取关键词（用于公众号/Reddit）', 'agent 智能体') || 'agent';
  const btn = document.getElementById('seedBtn');
  btn.disabled = true;
  btn.textContent = '抓取中...';
  try {
    const res = await fetch('/api/collect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 5 })
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'collect failed');
    state = data.state;
    renderAll();
  } catch (e) {
    alert('抓取失败：' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '模拟抓取一批';
  }
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  location.href = '/login';
}

function exportData() {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aihot-state-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));
document.getElementById('seedBtn').addEventListener('click', collect);
document.getElementById('exportBtn').addEventListener('click', exportData);
document.getElementById('logoutBtn').addEventListener('click', logout);
document.getElementById('importInput').parentElement.style.display = 'none';

(async () => {
  const ok = await loadMe();
  if (!ok) return;
  await Promise.all([loadState(), loadAdminData()]);
  renderAll();
  switchView('news');
})();
