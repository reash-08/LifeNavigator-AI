import './style.css';
import { buildProfilePayload } from './profile.js';
import {
  getDefaultFilters,
  buildSchemeSearchParams,
  resetFiltersState,
  clearAuthSession,
  initAuthSession,
} from './filters.js';
import { renderAssistantAnswer, escapeHtml } from './markdown.js';

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const root = document.querySelector('#app');
const state = { token: localStorage.getItem('ln_token'), user: null, profile: null, matches: [], schemes: [], schemeOptions: [], explore: [], active: 'overview', detailId: null, busy: false, chat: [], filters: getDefaultFilters(), adminTab: 'review', adminSchemes: [], pendingVersions: [], adminDocuments: [], editingScheme: null, editingRules: [] };
const icon = (name) => ({ home: '⌂', person: '◉', chat: '✳', logout: '↗', arrow: '↗', leaf: '✳', search: '⌕', close: '×', shield: '✓' })[name] || '•';

async function api(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}), ...options.headers };
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && state.token) { logout(false); throw new Error('Your session has expired. Please sign in again.'); }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const data = await response.json(); message = data.detail || message; } catch { /* use status */ }
    throw new Error(Array.isArray(message) ? message.map((item) => item.msg).join(', ') : message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function notice(message, kind = 'error') {
  const el = document.querySelector('#notice');
  if (!el) return;
  el.textContent = message; el.className = `notice ${kind}`; el.hidden = false;
  window.clearTimeout(notice.timer); notice.timer = window.setTimeout(() => { el.hidden = true; }, 5200);
}

function authView(mode = 'login') {
  const registering = mode === 'register';
  root.innerHTML = `<main class="auth-shell"><section class="auth-art"><a class="brand" href="#"><span class="brand-mark">${icon('leaf')}</span><span>Life<span class="brand-light">Navigator</span></span></a><div class="art-copy"><span class="eyebrow">A clearer path to support</span><h1>Good support<br>should be easier<br>to find.</h1><p>One place to explore government benefits, understand your options, and take the next step with confidence.</p><div class="art-note"><span class="note-icon">${icon('shield')}</span><span>Your information stays private and is used only to personalize your experience.</span></div></div><span class="art-foot">Built for every chapter of life.</span></section><section class="auth-panel"><div class="auth-card"><span class="eyebrow">YOUR BENEFITS COMPANION</span><h2>${registering ? 'Create your account' : 'Welcome back'}</h2><p class="muted">${registering ? 'Start discovering support made for you.' : 'Sign in to continue your journey.'}</p><div id="notice" class="notice" hidden></div><form id="auth-form"><label>Email address<input name="email" type="email" autocomplete="email" placeholder="you@example.com" required></label><label>Password<input name="password" type="password" minlength="${registering ? 12 : 1}" maxlength="128" autocomplete="${registering ? 'new-password' : 'current-password'}" placeholder="${registering ? 'At least 12 characters' : 'Enter your password'}" required></label>${registering ? '<label>Confirm password<input name="confirm" type="password" minlength="12" autocomplete="new-password" required></label>' : ''}<button class="button primary full" type="submit" id="auth-submit">${registering ? 'Create account' : 'Sign in'} <span>${icon('arrow')}</span></button></form><p class="auth-switch">${registering ? 'Already have an account?' : 'New to LifeNavigator?'} <button class="text-button" id="auth-toggle">${registering ? 'Sign in' : 'Create an account'}</button></p><p class="tiny muted">By continuing, you agree to keep your account details secure.</p></div></section></main>`;
  document.querySelector('#auth-toggle').onclick = () => authView(registering ? 'login' : 'register');
  document.querySelector('#auth-form').onsubmit = async (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const email = form.get('email'); const password = form.get('password');
    if (registering && password !== form.get('confirm')) return notice('Your passwords do not match.');
    const button = document.querySelector('#auth-submit'); button.disabled = true; button.innerHTML = 'Please wait…';
    try {
      if (registering) await api('/api/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) });
      const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      initAuthSession(state, result.access_token);
      await loadApp();
    } catch (error) { notice(error.message); button.disabled = false; button.innerHTML = `${registering ? 'Create account' : 'Sign in'} <span>${icon('arrow')}</span>`; }
  };
}

function logout(render = true) {
  clearAuthSession(state);
  if (render) authView();
}

async function loadApp() {
  initAuthSession(state);
  root.innerHTML = '<main class="loading-screen"><span class="loading-mark">✳</span><b>Getting your space ready…</b><span class="muted">Connecting to your benefits companion</span></main>';
  try {
    state.user = await api('/api/users/me');
    try { state.profile = await api('/api/profile'); } catch (error) { if (!String(error.message).toLowerCase().includes('profile not found')) throw error; state.profile = null; }
    try { state.matches = await api('/api/eligibility/matches'); } catch { state.matches = []; }
    try { const response = await api('/api/schemes/search?active_only=true&limit=200'); state.schemes = response.results || []; } catch { state.schemes = []; }
    try { const response = await api('/api/schemes/search?active_only=false&limit=200'); state.schemeOptions = response.results || []; } catch { state.schemeOptions = state.schemes; }
    renderApp();
  } catch (error) { if (!state.token) authView(); else { authView(); notice(error.message); } }
}

function renderApp() {
  const name = state.profile?.full_name?.split(' ')[0] || state.user?.email?.split('@')[0] || 'there';
  const titles = { overview: 'Overview', explore: 'Explore schemes', profile: 'My profile', account: 'Account', assistant: 'AI assistant', detail: 'Scheme details', admin: 'Scheme administration' };
  root.innerHTML = `<div class="app-shell"><aside class="sidebar"><a class="brand" href="#" data-page="overview"><span class="brand-mark">${icon('leaf')}</span><span>Life<span class="brand-light">Navigator</span></span></a><div class="side-label">YOUR SPACE</div><nav><button class="nav-item ${state.active === 'overview' ? 'selected' : ''}" data-page="overview"><span class="nav-icon">${icon('home')}</span>Home</button><button class="nav-item ${state.active === 'explore' || state.active === 'detail' ? 'selected' : ''}" data-page="explore"><span class="nav-icon">${icon('search')}</span>Explore schemes</button><button class="nav-item ${state.active === 'profile' ? 'selected' : ''}" data-page="profile"><span class="nav-icon">${icon('person')}</span>My profile</button><button class="nav-item ${state.active === 'account' ? 'selected' : ''}" data-page="account"><span class="nav-icon">◉</span>Account</button><button class="nav-item ${state.active === 'assistant' ? 'selected' : ''}" data-page="assistant"><span class="nav-icon">${icon('chat')}</span>AI assistant<span class="nav-new">NEW</span></button>${state.user?.is_admin ? `<button class="nav-item ${state.active === 'admin' ? 'selected' : ''}" data-page="admin"><span class="nav-icon">${icon('shield')}</span>Admin dashboard</button>` : ''}</nav><div class="side-bottom"><div class="help-card"><div class="help-spark">✳</div><strong>Here to help</strong><p>Ask anything about benefits and support.</p><button class="help-link" data-page="assistant">Talk to your assistant <span>→</span></button></div><button class="account-row" data-page="account"><span class="avatar">${escapeHtml(name.slice(0, 1).toUpperCase())}</span><span class="account-name"><b>${escapeHtml(name)}</b><small>${escapeHtml(state.user?.email || '')}</small></span><span class="logout-icon">⌄</span></button></div></aside><main class="main-content"><header class="topbar"><span class="mobile-brand"><span class="brand-mark">${icon('leaf')}</span> LifeNavigator</span><span class="breadcrumb">Your space <span>/</span> ${titles[state.active] || titles.detail}</span><button class="profile-shortcut" data-page="account"><span class="avatar small">${escapeHtml(name.slice(0, 1).toUpperCase())}</span><span>${escapeHtml(name)}</span><span>⌄</span></button><button class="mobile-logout" id="mobile-logout" type="button">Sign out</button></header><div class="content-wrap"><div id="notice" class="notice" hidden></div><div id="page-content"></div></div></main></div>`;
  const isAssistant = state.active === 'assistant';
  const mainEl = root.querySelector('.main-content');
  const wrapEl = root.querySelector('.content-wrap');
  if (mainEl) mainEl.classList.toggle('assistant-main', isAssistant);
  if (wrapEl) wrapEl.classList.toggle('assistant-wrap', isAssistant);
  root.querySelectorAll('[data-page]').forEach((button) => { button.addEventListener('click', () => { state.active = button.dataset.page; renderApp(); }); });
  document.querySelector('#mobile-logout').onclick = () => logout();
  if (state.active === 'profile') renderProfile(); else if (state.active === 'assistant') renderAssistant(); else if (state.active === 'explore') renderExplore(); else if (state.active === 'detail') renderSchemeDetail(); else if (state.active === 'account') renderAccount(); else if (state.active === 'admin' && state.user?.is_admin) renderAdmin(); else renderOverview(name);
  root.querySelectorAll('[data-scheme-id]').forEach((button) => button.addEventListener('click', () => openScheme(button.dataset.schemeId)));
}

const statusInfo = (status) => ({ eligible: ['Eligible', 'status-good'], not_eligible: ['Not eligible', 'status-no'], not_confirmed: ['Needs more details', 'status-warn'], profile_required: ['Complete your profile', 'status-warn'], not_evaluated: ['Not assessed', 'status-neutral'] }[status] || ['Not assessed', 'status-neutral']);
function matchStatus(item) {
  const unknown = item.eligibility_verification_status !== 'verified' || (item.reasons || []).some((reason) => /missing|not confirmed|not verified|not registered|no verified eligibility/i.test(reason));
  return statusInfo(unknown ? 'not_confirmed' : item.eligible ? 'eligible' : 'not_eligible');
}
function schemeCard(item, match = false) {
  const status = match ? matchStatus(item) : null;
  const description = item.description || item.name || 'Explore this government support scheme.';
  const reasons = match && item.reasons?.length ? `<ul class="reason-list">${item.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>` : '';
  const docs = item.required_documents ? `<p class="scheme-meta"><b>Documents:</b> ${escapeHtml(item.required_documents)}</p>` : '';
  const source = item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.source_name || 'Official source')} ↗</a>` : '';
  const application = item.application_url ? `<a class="button secondary compact" href="${escapeHtml(item.application_url)}" target="_blank" rel="noopener noreferrer">View application ↗</a>` : '';
  const verification = item.verification_status && item.verification_status !== 'verified' ? `<span class="status status-warn">${escapeHtml(item.verification_status.replaceAll('_', ' '))}</span>` : '';
  return `<article class="scheme-card"><div class="scheme-top"><span class="scheme-icon">✳</span>${status ? `<span class="status ${status[1]}">${status[0]}</span>` : item.category ? `<span class="category-pill">${escapeHtml(item.category)}</span>` : ''}${verification}</div><h3>${escapeHtml(item.name)}</h3><p class="scheme-description">${escapeHtml(description)}</p>${item.benefit ? `<p class="benefit-line"><b>Support:</b> ${escapeHtml(item.benefit)}</p>` : ''}${item.state ? `<p class="scheme-meta">Available in ${escapeHtml(item.state)}</p>` : ''}${reasons}${docs}<div class="card-foot">${source}<button type="button" class="text-button" data-scheme-id="${item.id}">Details →</button>${application}</div></article>`;
}

function openScheme(id) { state.detailId = Number(id); state.active = 'detail'; renderApp(); }
async function renderExplore() {
  const content = document.querySelector('#page-content');
  const beneficiaries = [['Farmers', 'farmer'], ['Women', 'women'], ['Senior Citizens', 'senior'], ['Students', 'student'], ['Persons with Disabilities', 'disabil'], ['Unemployed', 'unemploy'], ['Workers', 'worker'], ['Entrepreneurs', 'entrepreneur'], ['Rural Households', 'rural'], ['Low-Income Households', 'low-income'], ['Widows', 'widow'], ['Agricultural Labourers', 'agricultural labour'], ['Ex-servicemen / families', 'ex-servic'], ['Fishermen / Fisherwomen', 'fish']];
  content.innerHTML = `<section class="page-intro"><span class="eyebrow">BROWSE & DISCOVER</span><h1>Explore government schemes</h1><p class="muted">Search official scheme information and narrow it by the people it serves.</p></section><form id="scheme-search" class="filter-panel"><label class="filter-search">Search by keyword<input name="q" value="${escapeHtml(state.filters.q)}" placeholder="Try farming, education, pension…"></label><label>Beneficiary<select name="beneficiary_group"><option value="">All beneficiaries</option>${beneficiaries.map(([label, value]) => `<option value="${value}" ${state.filters.beneficiary_group === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>Category<select name="category"><option value="">All categories</option>${[...new Set(state.schemeOptions.map((s) => s.category).filter(Boolean))].map((v) => `<option ${state.filters.category === v ? 'selected' : ''}>${escapeHtml(v)}</option>`).join('')}</select></label><label>State<select name="state"><option value="">All states</option>${[...new Set(state.schemeOptions.map((s) => s.state).filter(Boolean))].map((v) => `<option ${state.filters.state === v ? 'selected' : ''}>${escapeHtml(v)}</option>`).join('')}</select></label><label>Status<select name="active_only"><option value="true" ${state.filters.active_only === 'true' ? 'selected' : ''}>Active</option><option value="false" ${state.filters.active_only === 'false' ? 'selected' : ''}>All statuses</option></select></label><div class="filter-actions"><button class="button primary" type="submit" id="search-schemes-submit">Search schemes <span>⌕</span></button><button class="button secondary" type="button" id="reset-filters">Reset filters</button></div></form><div class="section-heading results-heading"><b id="scheme-count">Loading schemes…</b></div><div id="scheme-results" class="scheme-grid"></div>`;
  const form = content.querySelector('#scheme-search');
  form.onsubmit = async (event) => { event.preventDefault(); state.filters = Object.fromEntries(new FormData(form)); await searchSchemes(); };
  const resetBtn = content.querySelector('#reset-filters');
  if (resetBtn) {
    resetBtn.onclick = async () => {
      resetFiltersState(state);
      if (form) {
        form.reset();
        if (form.elements.q) form.elements.q.value = '';
        if (form.elements.beneficiary_group) form.elements.beneficiary_group.value = '';
        if (form.elements.category) form.elements.category.value = '';
        if (form.elements.state) form.elements.state.value = '';
        if (form.elements.active_only) form.elements.active_only.value = 'true';
      }
      await searchSchemes();
    };
  }
  await searchSchemes();
}
async function searchSchemes() {
  const target = document.querySelector('#scheme-results'); if (!target) return;
  const params = buildSchemeSearchParams(state.filters);
  try { const response = await api(`/api/schemes/search?${params}`); state.explore = response.results || []; }
  catch (error) { target.innerHTML = `<div class="empty-card"><b>Couldn’t load schemes</b><p>${escapeHtml(error.message)}</p></div>`; return; }
  const count = document.querySelector('#scheme-count'); if (count) count.textContent = `${state.explore.length} scheme${state.explore.length === 1 ? '' : 's'} found`;
  target.innerHTML = state.explore.length ? state.explore.map((item) => schemeCard(item)).join('') : '<div class="empty-card"><span>⌕</span><b>No schemes match these filters</b><p>Try another keyword or choose a broader beneficiary group.</p></div>';
  target.querySelectorAll('[data-scheme-id]').forEach((button) => button.addEventListener('click', () => openScheme(button.dataset.schemeId)));
}
async function renderSchemeDetail() {
  const content = document.querySelector('#page-content'); content.innerHTML = '<div class="empty-card"><b>Loading scheme details…</b></div>';
  try {
    const item = await api(`/api/schemes/${state.detailId}`); const match = state.matches.find((m) => m.id === item.id); const status = !state.profile ? ['Complete your profile', 'status-warn'] : match ? matchStatus(match) : ['Not assessed', 'status-neutral'];
    content.innerHTML = `<button class="text-button back-link" data-page="explore">← Back to schemes</button><section class="page-intro"><span class="eyebrow">${escapeHtml(item.category || 'GOVERNMENT SUPPORT')}</span><h1>${escapeHtml(item.name)}</h1><p class="muted">${escapeHtml(item.ministry || item.department || item.government_level || '')}</p></section><article class="detail-card"><div class="detail-status"><span class="status ${status[1]}">${status[0]}</span>${item.state ? `<span class="category-pill">${escapeHtml(item.state)}</span>` : ''}${item.verification_status && item.verification_status !== 'verified' ? `<span class="status status-warn">Source ${escapeHtml(item.verification_status)}</span>` : ''}</div><section><h2>About this scheme</h2><p>${escapeHtml(item.description)}</p></section><section><h2>Benefits</h2><p>${escapeHtml(item.benefit || 'No benefit details are recorded.')}</p></section><section><h2>Who may apply</h2><p>${escapeHtml((item.beneficiary_groups || []).join(', ') || 'Beneficiary group is not specified.')}</p>${match?.reasons?.length ? `<ul class="reason-list">${match.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>` : ''}${!state.profile ? '<p class="muted">Add your profile to see the backend eligibility assessment.</p>' : ''}${item.eligibility_verification_status !== 'verified' ? '<p class="verification">Eligibility criteria have not been verified. Check the official source before relying on an assessment.</p>' : ''}</section><section><h2>Documents required</h2><p>${escapeHtml(item.required_documents || 'Required documents are not listed in the available scheme data.')}</p>${item.application_deadline ? `<p><b>Application deadline:</b> ${escapeHtml(item.application_deadline)}</p>` : ''}</section><section><h2>How to apply</h2><p>${escapeHtml(item.application_process || (item.application_url ? 'Open the official application portal for current instructions. The application steps are not recorded in the available scheme data.' : 'Application instructions are not recorded in the available scheme data.'))}</p></section><div class="detail-actions">${item.application_url ? `<a class="button primary" href="${escapeHtml(item.application_url)}" target="_blank" rel="noopener noreferrer">Go to application ↗</a>` : ''}${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.source_name || 'Official source')} ↗</a>` : '<span class="muted tiny">No source link recorded</span>'}</div>${item.verification_status ? `<p class="verification">Source ${escapeHtml(item.verification_status)}${item.verified_at ? ` · checked ${escapeHtml(item.verified_at)}` : ''}</p>` : ''}</article>`;
    content.querySelector('[data-page="explore"]').onclick = () => { state.active = 'explore'; renderApp(); };
  } catch (error) { content.innerHTML = `<div class="empty-card"><b>Scheme details unavailable</b><p>${escapeHtml(error.message)}</p><button class="button secondary" data-page="explore">Back to schemes</button></div>`; content.querySelector('[data-page]').onclick = () => { state.active = 'explore'; renderApp(); }; }
}
function renderAccount() {
  const content = document.querySelector('#page-content');
  content.innerHTML = `<section class="page-intro"><span class="eyebrow">YOUR ACCOUNT</span><h1>Account settings</h1><p class="muted">Manage sign-in details and your LifeNavigator session.</p></section><section class="account-panel"><h2>Account details</h2><div class="account-detail"><span>Email address</span><b>${escapeHtml(state.user?.email || '')}</b></div><div class="account-detail"><span>Account type</span><b>${state.user?.is_admin ? 'Administrator' : 'Citizen account'}</b></div></section><section class="account-panel"><h2>Change password</h2><p class="muted">Use a new password with at least 12 characters.</p><form id="password-form" class="password-form"><label class="field">Current password<input name="current_password" type="password" autocomplete="current-password" required></label><label class="field">New password<input name="new_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label><label class="field">Confirm new password<input name="confirm_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required></label><button class="button primary" type="submit">Update password</button></form></section><section class="account-panel account-signout"><div><h2>Sign out</h2><p class="muted">End this session on this device.</p></div><button class="button secondary" id="account-logout">Sign out <span>↗</span></button></section>`;
  content.querySelector('#account-logout').onclick = () => logout();
  content.querySelector('#password-form').onsubmit = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); if (form.get('new_password') !== form.get('confirm_password')) return notice('Your new passwords do not match.'); const button = event.currentTarget.querySelector('button'); button.disabled = true; try { await api('/api/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password: form.get('current_password'), new_password: form.get('new_password') }) }); event.currentTarget.reset(); notice('Your password has been updated.', 'success'); } catch (error) { notice(error.message); } finally { button.disabled = false; } };
}

function renderOverview(name) {
  const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 18 ? 'Good afternoon' : 'Good evening';
  const matches = state.matches || []; const eligible = matches.filter((item) => item.eligible).length;
  const content = document.querySelector('#page-content');
  content.innerHTML = `<section class="welcome-row"><div><span class="eyebrow">YOUR PERSONAL BENEFITS SPACE</span><h1>${greeting}, ${escapeHtml(name)} <span class="wave">✳</span></h1><p class="muted">A little clarity can make a big difference. Let’s find support that fits your life.</p></div><button class="button primary" data-page="assistant">Ask your AI assistant <span>→</span></button></section>${!state.profile ? `<section class="profile-prompt"><div class="prompt-symbol">${icon('person')}</div><div><b>Make this space yours</b><p>Add a few details to get more relevant support suggestions.</p></div><button class="button secondary" data-page="profile">Set up your profile <span>→</span></button></section>` : ''}<section class="stat-grid"><article class="stat-card"><span class="stat-label">YOUR PROFILE</span><strong>${state.profile ? 'Ready' : 'Not set up'}</strong><small>${state.profile ? `Personalized for ${escapeHtml(state.profile.state)}` : 'Add details to personalize your experience'}</small></article><article class="stat-card"><span class="stat-label">POTENTIAL MATCHES</span><strong>${state.profile ? eligible : '—'}</strong><small>${state.profile ? `${eligible === 1 ? 'scheme may fit' : 'schemes may fit'} your profile` : 'Complete your profile to explore'}</small></article><article class="stat-card accent-stat"><span class="stat-label">NEED A HAND?</span><strong>Ask a question</strong><small>Get clear answers with official sources</small><button class="stat-action" data-page="assistant">Start a conversation →</button></article></section><section class="section-block"><div class="section-heading"><div><span class="eyebrow">PERSONALIZED FOR YOU</span><h2>Support that may fit</h2></div>${matches.length ? `<button class="text-button" data-page="assistant">Ask about these →</button>` : ''}</div>${!state.profile ? '<div class="empty-card"><span>✳</span><b>Your recommendations start with your story</b><p>Set up your profile and we’ll check it against available schemes.</p><button class="button secondary" data-page="profile">Complete your profile</button></div>' : matches.length ? `<div class="scheme-grid">${matches.slice(0, 4).map((item) => schemeCard(item, true)).join('')}</div>` : '<div class="empty-card"><span>✳</span><b>No matching schemes found yet</b><p>Try asking the assistant about a specific kind of support, or check back later.</p><button class="button secondary" data-page="assistant">Explore with the assistant</button></div>'}</section><section class="section-block browse-section"><div class="section-heading"><div><span class="eyebrow">BROWSE & DISCOVER</span><h2>Explore available schemes</h2></div><span class="muted tiny">${state.schemes.length} to explore</span></div>${state.schemes.length ? `<div class="scheme-grid">${state.schemes.slice(0, 6).map((item) => schemeCard(item)).join('')}</div>` : '<div class="empty-card compact-empty"><b>Scheme information is unavailable right now.</b><p>Please try again in a moment.</p></div>'}</section>`;
  wirePageButtons();
}

function wirePageButtons() { document.querySelectorAll('#page-content [data-page]').forEach((button) => { button.onclick = () => { state.active = button.dataset.page; renderApp(); }; }); }

const profileFields = [
  ['full_name', 'Full name', 'text', true, 'Personal'], ['age', 'Age', 'number', true, 'Personal'], ['gender', 'Gender', 'select', true, 'Personal', ['Prefer not to say', 'Woman', 'Man', 'Non-binary', 'Other']], ['marital_status', 'Marital status', 'select', false, 'Personal', ['Single', 'Married', 'Widowed', 'Divorced', 'Other']],
  ['state', 'State / union territory', 'text', true, 'Location'], ['district', 'District', 'text', false, 'Location'], ['pincode', 'PIN code', 'text', false, 'Location'], ['domicile_state', 'Domicile state', 'text', false, 'Location'], ['rural_or_urban', 'Area type', 'select', false, 'Location', ['Rural', 'Urban']],
  ['category', 'Social category', 'select', false, 'Background', ['General', 'SC', 'ST', 'OBC', 'Other']], ['minority_status', 'Minority community', 'boolean', false, 'Background'], ['education', 'Highest education', 'text', false, 'Background'], ['employment_status', 'Employment status', 'text', false, 'Work'], ['occupation', 'Occupation', 'text', false, 'Work'], ['beneficiary_group', 'Beneficiary group', 'text', false, 'Work'],
  ['annual_income', 'Annual household income (₹)', 'number', false, 'Income'], ['income_source', 'Main income source', 'text', false, 'Income'], ['income_certificate_available', 'Income certificate available', 'boolean', false, 'Income'], ['bpl_status', 'BPL household', 'boolean', false, 'Income'], ['ration_card_type', 'Ration card type', 'text', false, 'Income'],
  ['family_size', 'Family size', 'number', false, 'Family'], ['dependents', 'Dependents', 'number', false, 'Family'], ['has_disability', 'Person with disability', 'boolean', false, 'Family'], ['disability_type', 'Disability type', 'text', false, 'Family'], ['disability_percentage', 'Disability percentage', 'number', false, 'Family'], ['disability_certificate_available', 'Disability certificate available', 'boolean', false, 'Family'],
  ['is_farmer', 'Farmer', 'boolean', false, 'Agriculture'], ['land_ownership', 'Owns agricultural land', 'boolean', false, 'Agriculture'], ['land_area', 'Land area', 'number', false, 'Agriculture'], ['land_unit', 'Land unit', 'text', false, 'Agriculture'], ['crop_type', 'Main crop', 'text', false, 'Agriculture'], ['owns_house', 'Owns a house', 'boolean', false, 'Housing'], ['widow', 'Widowed', 'boolean', false, 'Family'], ['senior_citizen', 'Senior citizen', 'boolean', false, 'Family'],
];
function fieldHtml([key, label, type, required, _group, options]) {
  const value = state.profile?.[key]; const req = required ? 'required' : '';
  let control;
  if (type === 'select') control = `<select name="${key}" ${req}><option value="">Choose…</option>${options.map((option) => `<option ${value === option ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}</select>`;
  else if (type === 'boolean') control = `<select name="${key}"><option value="">Not specified</option><option value="true" ${value === true ? 'selected' : ''}>Yes</option><option value="false" ${value === false ? 'selected' : ''}>No</option></select>`;
  else control = `<input name="${key}" type="${type}" ${type === 'number' ? `min="${key === 'age' ? 1 : 0}" ${key === 'age' ? 'max="120"' : ''} step="${key === 'disability_percentage' || key === 'land_area' ? '0.1' : '1'}"` : `maxlength="${key === 'full_name' ? 100 : 150}"`} value="${value ?? ''}" ${req}>`;
  return `<label class="field">${label}${required ? ' <span class="required-star">*</span>' : ''}${control}</label>`;
}
function renderProfile() {
  const content = document.querySelector('#page-content');
  const groups = [...new Set(profileFields.map((item) => item[4]))];
  content.innerHTML = `<section class="page-intro"><span class="eyebrow">YOUR DETAILS</span><h1>Your profile</h1><p class="muted">Share what you’re comfortable with. These details help the backend find support that may fit you.</p></section><div class="privacy-note"><span>${icon('shield')}</span><span><b>Your information is private.</b> It is sent securely to personalize your benefits search. You can update it any time.</span></div><form id="profile-form" class="profile-form">${groups.map((group) => `<section class="form-section"><div class="form-section-head"><h2>${group}</h2>${group === 'Personal' ? '<span class="tiny muted">Required fields marked <i>*</i></span>' : ''}</div><div class="field-grid">${profileFields.filter((item) => item[4] === group).map(fieldHtml).join('')}</div></section>`).join('')}<div class="form-actions"><span class="tiny muted">You can leave any optional field blank.</span><button class="button primary" id="save-profile">${state.profile ? 'Save changes' : 'Save my profile'} <span>→</span></button></div></form>`;
  document.querySelector('#profile-form').onsubmit = async (event) => {
    event.preventDefault(); const button = document.querySelector('#save-profile'); button.disabled = true; button.textContent = 'Saving…';
    const data = buildProfilePayload(Object.fromEntries(new FormData(event.currentTarget)), profileFields);
    try { state.profile = await api('/api/profile', { method: state.profile ? 'PUT' : 'POST', body: JSON.stringify(data) }); state.matches = await api('/api/eligibility/matches'); state.active = 'overview'; renderApp(); notice('Your profile has been saved.', 'success'); } catch (error) { notice(error.message); button.disabled = false; button.innerHTML = `${state.profile ? 'Save changes' : 'Save my profile'} <span>→</span>`; }
  };
}

function smartScroll(thread, force = false) {
  if (!thread) return;
  const dist = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
  if (force || dist < 240) {
    requestAnimationFrame(() => {
      thread.scrollTo({ top: thread.scrollHeight, behavior: 'smooth' });
    });
  }
}

function createAgentResponseElement(data) {
  const message = document.createElement('div');
  message.className = 'assistant-message';
  const schemes = (data.schemes || []).map((scheme) => {
    const status = statusInfo(scheme.eligibility || 'not_evaluated');
    return `
      <article class="result-card">
        <div class="result-head">
          <b>${escapeHtml(scheme.name)}</b>
          <span class="status ${status[1]}">${status[0]}</span>
        </div>
        ${scheme.missing_profile_fields?.length ? `
          <p class="result-label">Profile details needed</p>
          <p class="result-detail">${scheme.missing_profile_fields.map(escapeHtml).join(', ')}</p>
        ` : ''}
        ${scheme.eligibility_reasons?.length ? `
          <p class="result-label">Eligibility reasons</p>
          <ul class="reason-list">${scheme.eligibility_reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>
        ` : ''}
        ${scheme.next_steps?.length ? `
          <p class="result-label">Next steps</p>
          <ul class="reason-list">${scheme.next_steps.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ul>
        ` : ''}
        <div class="result-links">
          ${scheme.application_url ? `<a class="button secondary compact" href="${escapeHtml(scheme.application_url)}" target="_blank" rel="noopener noreferrer">Official application ↗</a>` : ''}
          ${scheme.source_url ? `<a class="source-link" href="${escapeHtml(scheme.source_url)}" target="_blank" rel="noopener noreferrer">Official scheme information ↗</a>` : ''}
          <button class="text-button" type="button" data-agent-scheme="${scheme.scheme_id}">Scheme details →</button>
        </div>
      </article>
    `;
  }).join('');

  const sources = (data.sources || []).map((source) => `
    <li>
      <span class="source-kind">${escapeHtml(source.kind.replaceAll('_', ' '))}</span>
      <b>${escapeHtml(source.scheme_name)}</b>
      <p>${escapeHtml(source.text)}</p>
      ${source.source_url ? `<a href="${escapeHtml(source.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.source_name || 'View official source')} ↗</a>` : '<span class="tiny muted">No direct URL provided</span>'}
      ${source.verification_status ? `<small class="verification">${escapeHtml(source.verification_status)}${source.verified_at ? ` · checked ${escapeHtml(source.verified_at)}` : ''}</small>` : ''}
    </li>
  `).join('');

  const clarify = data.needs_clarification
    ? '<div class="clarification"><b>Could you share a little more?</b><p>A detail such as your location, age, or household situation may help narrow this down.</p></div>'
    : '';

  const insufficient = data.insufficient_evidence
    ? '<div class="evidence-note">I don’t have enough verified information to give a confident answer. Please check the official sources below.</div>'
    : '';

  message.innerHTML = `
    <div class="message-avatar">✳</div>
    <div class="message-content">
      ${renderAssistantAnswer(data.answer, data.sources)}
      ${schemes ? `<div class="agent-results"><p class="result-label">Relevant schemes found (${data.schemes.length})</p>${schemes}</div>` : ''}
      ${clarify}
      ${insufficient}
      ${sources ? `<details class="sources"><summary>Sources & citations (${data.sources.length})</summary><ol>${sources}</ol></details>` : '<p class="tiny muted">No sources were returned for this answer.</p>'}
    </div>
  `;

  message.querySelectorAll('[data-agent-scheme]').forEach((button) => {
    button.onclick = () => openScheme(button.dataset.agentScheme);
  });

  return message;
}

function appendMessage(text, kind = 'assistant', pushHistory = true) {
  const thread = document.querySelector('#chat-thread');
  const element = document.createElement('div');
  element.className = kind === 'user' ? 'user-message' : kind === 'error' ? 'error-message' : 'assistant-message';

  if (kind === 'user') {
    element.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  } else if (kind === 'error') {
    element.innerHTML = `<div class="error-icon">!</div><div class="error-text"><p>${escapeHtml(text)}</p></div>`;
  } else {
    element.innerHTML = `<div class="message-avatar">✳</div><div class="message-content"><p>${escapeHtml(text)}</p></div>`;
  }

  if (thread) {
    thread.append(element);
    smartScroll(thread, kind === 'user');
  }

  if (pushHistory) {
    state.chat.push({ role: kind, text, timestamp: Date.now() });
  }

  return element;
}

function appendPending() {
  const thread = document.querySelector('#chat-thread');
  const element = document.createElement('div');
  element.className = 'assistant-message pending-indicator';
  element.innerHTML = `
    <div class="message-avatar">✳</div>
    <div class="message-content">
      <div class="typing">
        <i></i><i></i><i></i>
        <span>Looking into verified sources…</span>
      </div>
    </div>
  `;
  if (thread) {
    thread.append(element);
    smartScroll(thread, true);
  }
  return element;
}

function appendAgentResponse(data, pushHistory = true) {
  const thread = document.querySelector('#chat-thread');
  const message = createAgentResponseElement(data);

  if (thread) {
    thread.append(message);
    smartScroll(thread, false);
  }

  if (pushHistory) {
    state.chat.push({ role: 'assistant', data, timestamp: Date.now() });
  }
}

function renderAssistant() {
  const content = document.querySelector('#page-content');
  if (content) content.className = 'page-assistant';
  const hasHistory = Array.isArray(state.chat) && state.chat.length > 0;

  content.innerHTML = `
    <section class="assistant-intro">
      <span class="eyebrow">YOUR BENEFITS COMPANION</span>
      <h1>Let’s find your way forward.</h1>
      <p class="muted">Ask a question about government benefits. I’ll explain what I can and point you to verified sources.</p>
    </section>
    <section class="chat-panel">
      <div class="chat-heading">
        <div class="assistant-avatar">✳</div>
        <div>
          <b>LifeNavigator assistant</b>
          <small id="chat-status"><span class="online-dot"></span> Ready to help</small>
        </div>
        <div class="chat-header-actions">
          ${hasHistory ? '<button class="clear-chat-button" id="clear-chat" type="button">Clear conversation</button>' : ''}
          <span class="secure-label">${icon('shield')} Secure</span>
        </div>
      </div>
      <div class="chat-thread" id="chat-thread">
        <div class="assistant-message welcome-message">
          <div class="message-avatar">✳</div>
          <div class="message-content">
            <p>Hi${state.profile?.full_name ? `, ${escapeHtml(state.profile.full_name.split(' ')[0])}` : ''}! I can help you explore benefits and understand next steps.</p>
            <p>${state.profile ? `I’ll use your saved profile for personalized eligibility checks. Your location is set to ${escapeHtml(state.profile.state)}.` : 'Adding your profile can make eligibility answers more personal.'} What would you like to know?</p>
            <div class="suggestions">
              ${['What support is available for families?', 'Am I eligible for farmer support?', 'What documents might I need?'].map((item) => `<button class="suggestion" type="button">${item} <span>↗</span></button>`).join('')}
            </div>
          </div>
        </div>
      </div>
      <form id="chat-form" class="chat-composer">
        <div class="composer-input-wrap">
          <textarea name="query" rows="1" maxlength="500" minlength="3" placeholder="Ask about a benefit, eligibility, or required documents…" required></textarea>
        </div>
        <button class="send-button" id="send-chat" type="submit" aria-label="Send question">↑</button>
        <div class="composer-note">Answers are source-grounded. Always verify details with the official source portal.</div>
      </form>
    </section>
  `;

  // Render previous conversation messages
  const thread = content.querySelector('#chat-thread');
  if (hasHistory && thread) {
    for (const msg of state.chat) {
      if (msg.role === 'user') {
        appendMessage(msg.text, 'user', false);
      } else if (msg.role === 'assistant' && msg.data) {
        appendAgentResponse(msg.data, false);
      } else if (msg.role === 'error') {
        appendMessage(msg.text, 'error', false);
      }
    }
    thread.scrollTop = thread.scrollHeight;
  }

  // Clear chat handler
  const clearBtn = content.querySelector('#clear-chat');
  if (clearBtn) {
    clearBtn.onclick = () => {
      state.chat = [];
      renderAssistant();
    };
  }

  // Suggestion buttons
  content.querySelectorAll('.suggestion').forEach((button) => {
    button.onclick = () => {
      const textarea = content.querySelector('[name="query"]');
      if (textarea) {
        textarea.value = button.textContent.replace('↗', '').trim();
        textarea.focus();
        content.querySelector('#chat-form').requestSubmit();
      }
    };
  });

  // Textarea auto-resize and Enter key submission
  const textarea = content.querySelector('[name="query"]');
  if (textarea) {
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 42), 120)}px`;
    });
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        content.querySelector('#chat-form').requestSubmit();
      }
    });
  }

  // Chat form submit handler
  const form = content.querySelector('#chat-form');
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (state.busy) return;

    const input = form.querySelector('textarea');
    const query = input.value.trim();
    if (query.length < 3) {
      input.focus();
      return;
    }

    state.busy = true;
    const submitBtn = content.querySelector('#send-chat');
    const statusEl = content.querySelector('#chat-status');
    submitBtn.disabled = true;
    input.disabled = true;
    if (statusEl) statusEl.innerHTML = '<span class="online-dot online-busy"></span> Searching verified records…';

    appendMessage(query, 'user', true);
    input.value = '';
    input.style.height = 'auto';

    const pending = appendPending();

    try {
      const response = await api('/api/agent/query', { method: 'POST', body: JSON.stringify({ query }) });
      pending.remove();
      appendAgentResponse(response, true);
    } catch (error) {
      pending.remove();
      appendMessage(`I couldn’t complete that request: ${error.message}. Please try again.`, 'error', true);
    } finally {
      state.busy = false;
      submitBtn.disabled = false;
      input.disabled = false;
      if (statusEl) statusEl.innerHTML = '<span class="online-dot"></span> Ready to help';
      input.focus();

      // Ensure clear button exists in header if we now have messages
      if (!content.querySelector('#clear-chat')) {
        const actions = content.querySelector('.chat-header-actions');
        if (actions) {
          const btn = document.createElement('button');
          btn.className = 'clear-chat-button';
          btn.id = 'clear-chat';
          btn.type = 'button';
          btn.textContent = 'Clear conversation';
          btn.onclick = () => {
            state.chat = [];
            renderAssistant();
          };
          actions.prepend(btn);
        }
      }
    }
  };
}

async function renderAdmin() {
  const content = document.querySelector('#page-content');
  content.innerHTML = '<div class="empty-card"><b>Loading administration…</b></div>';
  try {
    const [schemes, pending, verified, documents, sources, syncStatus] = await Promise.all([
      api('/api/schemes'),
      api('/api/admin/scheme-data/versions/pending'),
      api('/api/admin/scheme-data/versions?verification_status=verified'),
      api('/api/admin/scheme-data/documents'),
      api('/api/admin/scheme-data/sources').catch(() => []),
      api('/api/admin/scheme-data/sync-status').catch(() => null),
    ]);
    state.adminSchemes = schemes;
    state.pendingVersions = pending;
    state.verifiedVersions = verified;
    state.adminDocuments = documents;
    state.adminSources = sources;
    state.syncStatus = syncStatus;
  } catch (error) {
    content.innerHTML = `<div class="empty-card"><b>Administration data could not be loaded</b><p>${escapeHtml(error.message)}</p></div>`;
    return;
  }
  content.innerHTML = `<section class="page-intro"><span class="eyebrow">CONTENT MANAGEMENT</span><h1>Scheme administration</h1><p class="muted">Review source-backed changes, maintain scheme records and rules, manage authorized government sources, and monitor RAG indexing.</p></section><div class="admin-stats"><article><small>SCHEMES</small><b>${state.adminSchemes.length}</b></article><article><small>AWAITING REVIEW</small><b>${state.pendingVersions.length}</b></article><article><small>OFFICIAL SOURCES</small><b>${state.adminSources?.length || 0}</b></article><article><small>OFFICIAL DOCUMENTS</small><b>${state.adminDocuments.length}</b></article></div><div class="admin-tabs"><button class="${state.adminTab === 'review' ? 'active' : ''}" data-admin-tab="review">Review & expire</button><button class="${state.adminTab === 'schemes' ? 'active' : ''}" data-admin-tab="schemes">Schemes & rules</button><button class="${state.adminTab === 'documents' ? 'active' : ''}" data-admin-tab="documents">Documents</button><button class="${state.adminTab === 'sources' ? 'active' : ''}" data-admin-tab="sources">Sources & sync</button><button class="${state.adminTab === 'diagnostics' ? 'active' : ''}" data-admin-tab="diagnostics">RAG diagnostics</button></div><div id="admin-panel"></div>`;
  content.querySelectorAll('[data-admin-tab]').forEach((button) => {
    button.onclick = () => {
      state.adminTab = button.dataset.adminTab;
      renderAdmin();
    };
  });
  if (state.adminTab === 'review') renderAdminReviews();
  else if (state.adminTab === 'schemes') renderAdminSchemes();
  else if (state.adminTab === 'sources') renderAdminSources();
  else if (state.adminTab === 'diagnostics') renderAdminDiagnostics();
  else renderAdminDocuments();
}

function renderAdminReviews() {
  const panel = document.querySelector('#admin-panel');
  const pendingCards = state.pendingVersions.map((version) => {
    const snapshot = version.snapshot || {};
    return `<article class="admin-card"><div class="admin-card-top"><div><span class="eyebrow">PENDING · VERSION ${version.version_number}</span><h2>${escapeHtml(version.scheme_name)}</h2></div><span class="status status-warn">Needs review</span></div><p>${escapeHtml(version.change_summary || 'New or updated scheme information')}</p><div class="admin-meta"><span>Source: ${escapeHtml(version.source_name || 'Not registered')}</span>${version.source_url ? `<a href="${escapeHtml(version.source_url)}" target="_blank" rel="noopener noreferrer">Open cited source ↗</a>` : ''}<span>Imported ${escapeHtml(version.imported_at || '')}</span></div><details><summary>Review proposed content</summary><dl class="snapshot-grid">${[['Description', snapshot.description], ['Benefits', snapshot.benefit], ['Who may apply', (snapshot.beneficiary_groups || []).join(', ')], ['Required documents', snapshot.required_documents], ['Application link', snapshot.application_url], ['Eligibility rules', (snapshot.eligibility_rules || []).length]].filter(([, value]) => value !== undefined && value !== null && value !== '').map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl></details><form class="review-form" data-review-id="${version.id}"><label>Eligibility status<select name="eligibility_verification_status"><option value="unverified">Unverified</option><option value="not_confirmed">Not confirmed</option><option value="verified" ${!(snapshot.eligibility_rules || []).length ? 'disabled' : ''}>Verified from source${!(snapshot.eligibility_rules || []).length ? ' (add rules first)' : ''}</option></select></label><label>Review note<input name="notes" maxlength="2000" placeholder="What did you verify? (optional)"></label><div class="admin-actions"><button class="button primary" name="decision" value="verified">Approve version</button><button class="button secondary" name="decision" value="rejected">Reject</button></div><p class="tiny muted">Approving a version requires an active registered HTTPS source. Eligibility can be verified only when explicit rules are included.</p></form></article>`;
  }).join('');
  const expireCards = state.verifiedVersions.map((version) => `<article class="admin-card compact-admin-card"><div><span class="eyebrow">VERIFIED · VERSION ${version.version_number}</span><h2>${escapeHtml(version.scheme_name)}</h2><p>${escapeHtml(version.source_name || 'Source unavailable')} · ${escapeHtml(version.verified_at || '')}</p></div><button class="button secondary" data-expire-version="${version.id}">Mark expired</button></article>`).join('');
  panel.innerHTML = `<section class="admin-section"><div class="section-heading"><div><h2>Pending source review</h2><p class="muted">Approval publishes this proposed snapshot. Review the source and eligibility evidence first.</p></div></div>${pendingCards || '<div class="empty-card"><b>No versions need review</b><p>Imported changes will appear here for an administrator decision.</p></div>'}</section><section class="admin-section"><div class="section-heading"><div><h2>Verified versions</h2><p class="muted">Expire a verified version when its published terms are no longer current.</p></div></div>${expireCards || '<p class="muted">There are no verified versions to expire.</p>'}</section>`;
  panel.querySelectorAll('.review-form').forEach((form) => { form.onsubmit = async (event) => { event.preventDefault(); const submitter = event.submitter; const values = Object.fromEntries(new FormData(form)); try { await api(`/api/admin/scheme-data/versions/${form.dataset.reviewId}/review`, { method: 'POST', body: JSON.stringify({ decision: submitter.value, eligibility_verification_status: values.eligibility_verification_status, notes: values.notes || null }) }); notice(submitter.value === 'verified' ? 'Scheme version approved.' : 'Scheme version rejected.', 'success'); renderAdmin(); } catch (error) { notice(error.message); } }; });
  panel.querySelectorAll('[data-expire-version]').forEach((button) => { button.onclick = async () => { if (!window.confirm('Mark this verified version as expired?')) return; try { await api(`/api/admin/scheme-data/versions/${button.dataset.expireVersion}/review`, { method: 'POST', body: JSON.stringify({ decision: 'expired', notes: 'Expired by administrator' }) }); notice('Scheme version marked expired.', 'success'); renderAdmin(); } catch (error) { notice(error.message); } }; });
}

function adminInput(label, name, value = '', type = 'text', attrs = '') {
  return `<label>${label}<input name="${name}" type="${type}" value="${escapeHtml(value ?? '')}" ${attrs}></label>`;
}

function renderAdminSchemes() {
  const panel = document.querySelector('#admin-panel');
  const rows = state.adminSchemes.map((scheme) => `<article class="admin-scheme-row"><div class="admin-scheme-info"><span class="status ${scheme.verification_status === 'verified' ? 'status-good' : 'status-warn'}">${escapeHtml(scheme.verification_status || 'unverified')}</span><h3>${escapeHtml(scheme.name)}</h3><p>${escapeHtml(scheme.category || 'Uncategorized')} · ${escapeHtml(scheme.state || scheme.government_level || 'Location not specified')}</p><small>Eligibility: ${escapeHtml(scheme.eligibility_verification_status || 'unverified')} · ${scheme.is_active ? 'Active' : 'Inactive'}</small></div><div class="admin-actions"><button class="button secondary compact" data-edit-scheme="${scheme.id}">Edit record</button><button class="button secondary compact" data-edit-rules="${scheme.id}">Eligibility rules (${scheme.eligibility_rules?.length || 0})</button></div></article>`).join('');
  panel.innerHTML = `<div class="section-heading admin-list-heading"><div><h2>Scheme records</h2><p class="muted">Unverified records stay labelled; adding criteria here does not verify them.</p></div><button class="button primary" id="new-scheme">Add scheme</button></div><div class="admin-scheme-list">${rows || '<div class="empty-card">No schemes found.</div>'}</div><div id="scheme-editor"></div><div id="rules-editor"></div>`;
  panel.querySelector('#new-scheme').onclick = () => { state.editingScheme = null; renderSchemeEditor(); };
  panel.querySelectorAll('[data-edit-scheme]').forEach((button) => { button.onclick = () => { state.editingScheme = state.adminSchemes.find((scheme) => scheme.id === Number(button.dataset.editScheme)); renderSchemeEditor(); }; });
  panel.querySelectorAll('[data-edit-rules]').forEach((button) => { button.onclick = () => renderRuleEditor(Number(button.dataset.editRules)); });
}

function renderSchemeEditor() {
  const target = document.querySelector('#scheme-editor'); if (!target) return;
  const scheme = state.editingScheme || {};
  target.innerHTML = `<section class="admin-card"><div class="section-heading"><div><span class="eyebrow">${scheme.id ? 'EDIT SCHEME' : 'NEW SCHEME'}</span><h2>${scheme.id ? escapeHtml(scheme.name) : 'Create scheme record'}</h2></div><button class="text-button" id="close-scheme-editor">Close</button></div><form id="scheme-editor-form" class="admin-form">${adminInput('Scheme name', 'name', scheme.name, 'text', 'required maxlength="255"')}<label>Description<textarea name="description" required>${escapeHtml(scheme.description || '')}</textarea></label><label>Benefits<textarea name="benefit" required>${escapeHtml(scheme.benefit || '')}</textarea></label>${adminInput('Category', 'category', scheme.category)}${adminInput('Subcategory', 'subcategory', scheme.subcategory)}${adminInput('Beneficiary groups (comma separated)', 'beneficiary_groups', (scheme.beneficiary_groups || []).join(', '))}${adminInput('State / region', 'state', scheme.state)}<label>Government level<select name="government_level"><option value="">Not specified</option>${['central', 'state', 'ut', 'local'].map((value) => `<option ${scheme.government_level === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>${adminInput('Ministry', 'ministry', scheme.ministry)}${adminInput('Department', 'department', scheme.department)}<label>Required documents<textarea name="required_documents">${escapeHtml(scheme.required_documents || '')}</textarea></label><label>How to apply (only source-backed steps)<textarea name="application_process">${escapeHtml(scheme.application_process || '')}</textarea></label>${adminInput('Official information URL', 'source_url', scheme.source_url, 'url')}${adminInput('Source name', 'source_name', scheme.source_name)}${adminInput('Official application URL', 'application_url', scheme.application_url, 'url')}<label>Source status<select name="verification_status">${['unverified', 'pending', 'verified', 'review_needed', 'expired', 'rejected'].map((value) => `<option ${scheme.verification_status === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label><label>Eligibility verification<select name="eligibility_verification_status">${['unverified', 'not_confirmed', 'verified'].map((value) => `<option ${((scheme.eligibility_verification_status || 'unverified') === value) ? 'selected' : ''}>${value}</option>`).join('')}</select></label><label class="admin-check"><input type="checkbox" name="is_active" ${scheme.is_active === false ? '' : 'checked'}> Active in discovery</label><div class="admin-form-actions"><button class="button primary">Save scheme</button></div></form></section>`;
  target.querySelector('#close-scheme-editor').onclick = () => { target.innerHTML = ''; };
  target.querySelector('#scheme-editor-form').onsubmit = async (event) => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = { ...values, beneficiary_groups: values.beneficiary_groups ? values.beneficiary_groups.split(',').map((item) => item.trim()).filter(Boolean) : [], is_active: event.currentTarget.elements.is_active.checked, min_age: scheme.min_age ?? null, max_age: scheme.max_age ?? null, education: scheme.education ?? null, employment_status: scheme.employment_status ?? null, max_annual_income: scheme.max_annual_income ?? null, application_deadline: scheme.application_deadline || null, verified_at: scheme.verified_at || null };
    try { await api(scheme.id ? `/api/schemes/${scheme.id}` : '/api/schemes', { method: scheme.id ? 'PUT' : 'POST', body: JSON.stringify(payload) }); notice('Scheme record saved.', 'success'); await renderAdmin(); } catch (error) { notice(error.message); }
  };
}

async function renderRuleEditor(schemeId) {
  const target = document.querySelector('#rules-editor'); if (!target) return;
  target.innerHTML = '<div class="admin-card">Loading eligibility rules…</div>';
  try { state.editingRules = await api(`/api/schemes/${schemeId}/rules`); }
  catch (error) { target.innerHTML = `<div class="empty-card"><b>Rules could not be loaded</b><p>${escapeHtml(error.message)}</p></div>`; return; }
  const rules = state.editingRules.map((rule) => `<div class="rule-row"><span><b>${escapeHtml(rule.field_name)} ${escapeHtml(rule.operator)} ${escapeHtml(rule.value)}</b><small>${rule.group_id ? `Group ${rule.group_id} · ${escapeHtml(rule.logical_operator || 'AND')}` : 'Single condition'}</small></span><button class="text-button" data-delete-rule="${rule.id}">Remove</button></div>`).join('');
  const fields = ['age', 'gender', 'state', 'domicile_state', 'district', 'category', 'minority_status', 'education', 'employment_status', 'occupation', 'beneficiary_group', 'annual_income', 'income_certificate_available', 'bpl_status', 'family_size', 'dependents', 'has_disability', 'disability_type', 'disability_percentage', 'disability_certificate_available', 'is_farmer', 'land_ownership', 'land_area', 'land_unit', 'crop_type', 'owns_house', 'widow', 'senior_citizen'];
  target.innerHTML = `<section class="admin-card"><div class="section-heading"><div><span class="eyebrow">ELIGIBILITY RULES</span><h2>${escapeHtml(state.adminSchemes.find((item) => item.id === schemeId)?.name || 'Scheme')}</h2><p class="muted">Only add conditions that you can support from official scheme material.</p></div><button class="text-button" id="close-rules">Close</button></div><div class="rule-list">${rules || '<p class="muted">No active structured rules. Eligibility will remain unconfirmed.</p>'}</div><form id="rule-form" class="admin-form rule-form"><label>Profile field<select name="field_name">${fields.map((field) => `<option>${field}</option>`).join('')}</select></label><label>Comparison<select name="operator">${['equals', 'not_equals', 'lt', 'lte', 'gt', 'gte', 'in', 'not_in', 'contains'].map((op) => `<option>${op}</option>`).join('')}</select></label>${adminInput('Rule value', 'value', '', 'text', 'required')}<label>Rule group (optional)<input name="group_id" type="number" min="1"></label><label>Group logic<select name="logical_operator"><option value="">Not grouped</option><option>AND</option><option>OR</option></select></label><button class="button primary">Add eligibility rule</button></form></section>`;
  target.querySelector('#close-rules').onclick = () => { target.innerHTML = ''; };
  target.querySelector('#rule-form').onsubmit = async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); const payload = { ...values, group_id: values.group_id ? Number(values.group_id) : null, logical_operator: values.logical_operator || null }; try { await api(`/api/schemes/${schemeId}/rules`, { method: 'POST', body: JSON.stringify(payload) }); notice('Eligibility rule added. Verify it against official guidance before marking eligibility as verified.', 'success'); renderRuleEditor(schemeId); } catch (error) { notice(error.message); } };
  target.querySelectorAll('[data-delete-rule]').forEach((button) => { button.onclick = async () => { try { await api(`/api/schemes/${schemeId}/rules/${button.dataset.deleteRule}`, { method: 'DELETE' }); renderRuleEditor(schemeId); } catch (error) { notice(error.message); } }; });
}

function renderAdminDocuments() {
  const panel = document.querySelector('#admin-panel');
  panel.innerHTML = `<section class="admin-card"><span class="eyebrow">SOURCE-BACKED RETRIEVAL</span><h2>Ingest an official document</h2><p class="muted">Paste text copied from an official document and record its exact HTTPS source. LifeNavigator does not fetch or scrape scheme portals.</p><form id="document-form" class="admin-form"><label>Scheme<select name="scheme_id" required><option value="">Choose a scheme…</option>${state.adminSchemes.map((scheme) => `<option value="${scheme.id}">${escapeHtml(scheme.name)}</option>`).join('')}</select></label>${adminInput('Document title', 'title')} ${adminInput('Source name', 'source_name', '', 'text', 'required')}${adminInput('Official HTTPS source URL', 'source_url', '', 'url', 'required') }<label>Document text<textarea name="content" required maxlength="2000000" rows="10" placeholder="Paste official source text here…"></textarea></label><p class="tiny muted">Up to 2 MB of text. Duplicate documents are detected by content hash.</p><button class="button primary">Ingest document</button></form></section><section class="admin-section"><div class="section-heading"><div><h2>Ingested documents</h2><p class="muted">Each item keeps its source URL and extracted text hash.</p></div></div><div class="admin-document-list">${state.adminDocuments.map((doc) => `<article class="admin-document"><div><b>${escapeHtml(doc.title || doc.source_name)}</b><small>${escapeHtml(state.adminSchemes.find((item) => item.id === doc.scheme_id)?.name || `Scheme ${doc.scheme_id}`)} · ${doc.chunk_count} text chunks · Status: ${escapeHtml(doc.ingestion_status || 'indexed')}</small></div><div class="admin-actions"><a href="${escapeHtml(doc.source_url)}" target="_blank" rel="noopener noreferrer" class="source-link">Official source ↗</a><button class="button secondary compact" data-reindex-doc="${doc.id}">Reindex</button><button class="text-button" data-delete-doc="${doc.id}">Remove</button></div></article>`).join('') || '<div class="empty-card"><b>No source documents ingested</b><p>Available document text will appear here after an administrator adds it.</p></div>'}</div></section>`;
  panel.querySelector('#document-form').onsubmit = async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); values.scheme_id = Number(values.scheme_id); try { const result = await api('/api/admin/scheme-data/documents', { method: 'POST', body: JSON.stringify(values) }); notice(result.created ? `Document ingested into ${result.chunk_count} searchable sections.` : 'This document is already in the corpus.', 'success'); renderAdmin(); } catch (error) { notice(error.message); } };
  panel.querySelector('[name="scheme_id"]').onchange = (event) => { const scheme = state.adminSchemes.find((item) => item.id === Number(event.target.value)); panel.querySelector('[name="source_name"]').value = scheme?.source_name || ''; panel.querySelector('[name="source_url"]').value = scheme?.source_url || ''; };
  panel.querySelectorAll('[data-reindex-doc]').forEach((button) => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        await api(`/api/admin/scheme-data/documents/${button.dataset.reindexDoc}/reindex`, { method: 'POST' });
        notice('Document chunks reindexed with embeddings.', 'success');
        renderAdmin();
      } catch (error) {
        notice(error.message);
        button.disabled = false;
      }
    };
  });
  panel.querySelectorAll('[data-delete-doc]').forEach((button) => {
    button.onclick = async () => {
      if (!window.confirm('Delete this ingested document and its indexed chunks?')) return;
      try {
        await api(`/api/admin/scheme-data/documents/${button.dataset.deleteDoc}`, { method: 'DELETE' });
        notice('Document removed from corpus.', 'success');
        renderAdmin();
      } catch (error) {
        notice(error.message);
      }
    };
  });
}

function renderAdminSources() {
  const panel = document.querySelector('#admin-panel');
  const sync = state.syncStatus || {};
  const sourcesList = (state.adminSources || []).map((source) => `
    <article class="admin-scheme-row">
      <div class="admin-scheme-info">
        <span class="status ${source.status === 'healthy' ? 'status-good' : 'status-warn'}">${escapeHtml(source.status || 'unknown')}</span>
        <h3>${escapeHtml(source.source_name)}</h3>
        <p>${escapeHtml(source.source_type || 'official_portal')} · Sync interval: ${source.sync_interval_hours || 24}h · Status: ${source.is_active ? 'Active' : 'Disabled'}</p>
        <small>${source.last_checked ? `Last checked: ${escapeHtml(source.last_checked)}` : 'Not yet checked'} ${source.last_successful_sync ? `· Last success: ${escapeHtml(source.last_successful_sync)}` : ''}</small>
      </div>
      <div class="admin-actions">
        <a href="${escapeHtml(source.source_url)}" target="_blank" rel="noopener noreferrer" class="source-link">Open source ↗</a>
        <button class="button secondary compact" data-toggle-source="${source.id}" data-active="${source.is_active}">${source.is_active ? 'Disable' : 'Enable'}</button>
      </div>
    </article>
  `).join('');

  panel.innerHTML = `
    <section class="admin-card">
      <div class="section-heading">
        <div>
          <span class="eyebrow">AUTOMATED SYNCHRONIZATION</span>
          <h2>Scheduled daily synchronization</h2>
          <p class="muted">Daily scheduler polls configured government sources for new and updated welfare programs.</p>
        </div>
        <button class="button primary" id="sync-now-button" ${sync.is_running ? 'disabled' : ''}>${sync.is_running ? 'Sync in progress…' : 'Sync now'}</button>
      </div>
      <div class="admin-meta">
        <span>Scheduler: <b>${sync.scheduler_running ? 'Active (Background worker running)' : 'Idle'}</b></span>
        <span>Interval: <b>${sync.sync_interval_hours || 24} hours</b></span>
        <span>Last synchronization: <b>${escapeHtml(sync.last_sync_time || 'None recorded')}</b></span>
        <span>Next run: <b>${escapeHtml(sync.next_scheduled_sync || 'Scheduled daily')}</b></span>
      </div>
    </section>

    <section class="admin-card">
      <div class="section-heading">
        <div>
          <span class="eyebrow">SOURCE REGISTRY</span>
          <h2>Register authorized government source</h2>
          <p class="muted">Add verified government portals or open APIs (must be official HTTPS domains).</p>
        </div>
      </div>
      <form id="source-form" class="admin-form">
        ${adminInput('Source name', 'source_name', '', 'text', 'required maxlength="200" placeholder="e.g. National Portal of India"')}
        ${adminInput('Official HTTPS source URL', 'source_url', '', 'url', 'required maxlength="1000" placeholder="https://india.gov.in"')}
        ${adminInput('API / Feed endpoint URL (optional)', 'api_url', '', 'url', 'maxlength="1000" placeholder="https://..."')}
        ${adminInput('Provider / Department', 'provider', '', 'text', 'maxlength="300" placeholder="e.g. Ministry of Agriculture"')}
        <label>Source type
          <select name="source_type">
            <option value="official_portal">Official government portal</option>
            <option value="api_endpoint">Permitted API / JSON feed</option>
            <option value="downloadable_circular">Circular / Notification download</option>
          </select>
        </label>
        ${adminInput('Sync interval (hours)', 'sync_interval_hours', '24', 'number', 'min="1" max="168" required')}
        <label>Notes (optional)
          <textarea name="notes" placeholder="Authorization details, coverage scope..."></textarea>
        </label>
        <div class="admin-form-actions">
          <button class="button primary">Register source</button>
        </div>
      </form>
    </section>

    <section class="admin-section">
      <div class="section-heading">
        <div>
          <h2>Configured government sources (${(state.adminSources || []).length})</h2>
          <p class="muted">Active sources are checked during scheduled and manual synchronizations.</p>
        </div>
      </div>
      <div class="admin-scheme-list">
        ${sourcesList || '<div class="empty-card">No sources registered.</div>'}
      </div>
    </section>
  `;

  panel.querySelector('#sync-now-button').onclick = async () => {
    const btn = panel.querySelector('#sync-now-button');
    btn.disabled = true;
    btn.textContent = 'Synchronizing…';
    try {
      const res = await api('/api/admin/scheme-data/sync-now', { method: 'POST' });
      const rep = res.report || {};
      notice(`Synchronization completed: ${rep.new_count || 0} new discovered, ${rep.changed_count || 0} updated, ${rep.errors?.length || 0} errors.`, 'success');
      await renderAdmin();
    } catch (error) {
      notice(error.message);
      btn.disabled = false;
      btn.textContent = 'Sync now';
    }
  };

  panel.querySelector('#source-form').onsubmit = async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    values.sync_interval_hours = Number(values.sync_interval_hours) || 24;
    try {
      await api('/api/admin/scheme-data/sources', { method: 'POST', body: JSON.stringify(values) });
      notice('Government source registered successfully.', 'success');
      renderAdmin();
    } catch (error) {
      notice(error.message);
    }
  };

  panel.querySelectorAll('[data-toggle-source]').forEach((button) => {
    button.onclick = async () => {
      const sourceId = button.dataset.toggleSource;
      const currentActive = button.dataset.active === 'true';
      try {
        await api(`/api/admin/scheme-data/sources/${sourceId}`, {
          method: 'PUT',
          body: JSON.stringify({ is_active: !currentActive }),
        });
        notice(`Source ${currentActive ? 'disabled' : 'enabled'}.`, 'success');
        renderAdmin();
      } catch (error) {
        notice(error.message);
      }
    };
  });
}

async function renderAdminDiagnostics() {
  const panel = document.querySelector('#admin-panel');
  panel.innerHTML = '<div class="admin-card">Loading RAG diagnostics…</div>';
  let diag = null;
  try {
    diag = await api('/api/admin/scheme-data/diagnostics');
  } catch (error) {
    panel.innerHTML = `<div class="empty-card"><b>Could not load diagnostics</b><p>${escapeHtml(error.message)}</p></div>`;
    return;
  }

  panel.innerHTML = `
    <section class="admin-card">
      <div class="section-heading">
        <div>
          <span class="eyebrow">RAG & VECTOR OBSERVABILITY</span>
          <h2>Vector store and pipeline metrics</h2>
          <p class="muted">Live status of vector embeddings, hybrid retrieval indexing, and document provenance.</p>
        </div>
      </div>
      <div class="admin-stats">
        <article><small>TOTAL SCHEMES</small><b>${diag.total_schemes}</b></article>
        <article><small>TOTAL DOCUMENTS</small><b>${diag.total_documents}</b></article>
        <article><small>CHUNKS INDEXED</small><b>${diag.total_chunks}</b></article>
        <article><small>EMBEDDINGS STORED</small><b>${diag.embedded_chunks}</b></article>
      </div>
      <div class="admin-meta">
        <span>Embedding provider: <b>${escapeHtml(diag.embedding_provider)}</b></span>
        <span>Dimensions: <b>${diag.embedding_dimensions}d</b></span>
        <span>Configured sources: <b>${diag.total_sources} (${diag.healthy_sources} healthy)</b></span>
        <span>Last document ingested: <b>${escapeHtml(diag.last_document_ingested_at || 'None')}</b></span>
      </div>
    </section>

    <section class="admin-card">
      <div class="section-heading">
        <div>
          <span class="eyebrow">DIAGNOSTIC TEST QUERY</span>
          <h2>Test hybrid retrieval</h2>
          <p class="muted">Evaluate chunk scoring, keyword overlap, and semantic vector similarity in real time.</p>
        </div>
      </div>
      <form id="test-retrieval-form" class="admin-form">
        ${adminInput('Search query', 'query', '', 'text', 'required placeholder="e.g. farmer financial assistance"')}
        <label>Filter by scheme (optional)
          <select name="scheme_id">
            <option value="">All schemes</option>
            ${state.adminSchemes.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('')}
          </select>
        </label>
        ${adminInput('Max chunks', 'limit', '5', 'number', 'min="1" max="20" required')}
        <div class="admin-form-actions">
          <button class="button primary">Run test retrieval</button>
        </div>
      </form>
      <div id="retrieval-results" style="margin-top: 18px;"></div>
    </section>
  `;

  panel.querySelector('#test-retrieval-form').onsubmit = async (event) => {
    event.preventDefault();
    const resultsContainer = panel.querySelector('#retrieval-results');
    resultsContainer.innerHTML = '<p class="muted">Evaluating hybrid retrieval…</p>';
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = {
      query: values.query,
      scheme_id: values.scheme_id ? Number(values.scheme_id) : null,
      limit: Number(values.limit) || 5,
    };
    try {
      const res = await api('/api/admin/scheme-data/test-retrieval', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!res.results || !res.results.length) {
        resultsContainer.innerHTML = '<div class="empty-card compact-empty"><p class="muted">No relevant document chunks matched the query.</p></div>';
        return;
      }
      resultsContainer.innerHTML = `
        <div class="section-heading">
          <div>
            <h3>Retrieved evidence chunks (${res.results.length} matches)</h3>
          </div>
        </div>
        <div class="agent-results">
          ${res.results.map((r) => `
            <article class="result-card">
              <div class="result-head">
                <b>${escapeHtml(r.document_title)}</b>
                <span class="status status-good">Score: ${r.score}</span>
              </div>
              <p style="margin: 8px 0; font-size: 11px; line-height: 1.6; color: #45584a;">"${escapeHtml(r.excerpt)}"</p>
              <div class="admin-meta">
                <span>Source: ${escapeHtml(r.source_name)}</span>
                ${r.source_url ? `<a href="${escapeHtml(r.source_url)}" target="_blank" rel="noopener noreferrer" class="source-link">Source ↗</a>` : ''}
                <span>Chunk ID: ${r.chunk_id}</span>
              </div>
            </article>
          `).join('')}
        </div>
      `;
    } catch (error) {
      resultsContainer.innerHTML = `<div class="notice">${escapeHtml(error.message)}</div>`;
    }
  };
}

if (!state.token) authView(); else loadApp();
