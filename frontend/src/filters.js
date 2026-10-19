export const DEFAULT_FILTERS = {
  q: '',
  beneficiary_group: '',
  category: '',
  state: '',
  active_only: 'true',
};

export function getDefaultFilters() {
  return { ...DEFAULT_FILTERS };
}

export function isDefaultFilters(filters) {
  if (!filters) return false;
  return (
    (filters.q || '') === '' &&
    (filters.beneficiary_group || '') === '' &&
    (filters.category || '') === '' &&
    (filters.state || '') === '' &&
    String(filters.active_only) === 'true'
  );
}

export function buildSchemeSearchParams(filters = {}, limit = 200) {
  const merged = { ...DEFAULT_FILTERS, ...filters };
  return new URLSearchParams({
    q: merged.q || '',
    beneficiary_group: merged.beneficiary_group || '',
    category: merged.category || '',
    state: merged.state || '',
    active_only: String(merged.active_only === 'true' || merged.active_only === true),
    limit: String(limit),
  });
}

export function resetFiltersState(state) {
  if (!state) return;
  state.filters = getDefaultFilters();
  state.explore = [];
}

export function clearAuthSession(state, storage = (typeof localStorage !== 'undefined' ? localStorage : null), sessionStore = (typeof sessionStorage !== 'undefined' ? sessionStorage : null)) {
  if (state) {
    state.token = null;
    state.user = null;
    state.profile = null;
    state.matches = [];
    state.filters = getDefaultFilters();
    state.explore = [];
    state.active = 'overview';
    state.detailId = null;
    if (state.chat) state.chat = [];
  }
  if (storage) {
    try {
      storage.removeItem('ln_token');
      storage.removeItem('explore_filters');
    } catch {
      /* ignore */
    }
  }
  if (sessionStore) {
    try {
      sessionStore.removeItem('explore_filters');
    } catch {
      /* ignore */
    }
  }
}

export function initAuthSession(state, token = null, storage = (typeof localStorage !== 'undefined' ? localStorage : null)) {
  if (state) {
    if (token) state.token = token;
    state.filters = getDefaultFilters();
    state.explore = [];
    state.active = 'overview';
    state.detailId = null;
  }
  if (storage && token) {
    try {
      storage.setItem('ln_token', token);
      storage.removeItem('explore_filters');
    } catch {
      /* ignore */
    }
  }
}
