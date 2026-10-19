import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_FILTERS,
  getDefaultFilters,
  isDefaultFilters,
  buildSchemeSearchParams,
  resetFiltersState,
  clearAuthSession,
  initAuthSession,
} from '../src/filters.js';

test('DEFAULT_FILTERS defines the expected initial filter state', () => {
  assert.deepEqual(DEFAULT_FILTERS, {
    q: '',
    beneficiary_group: '',
    category: '',
    state: '',
    active_only: 'true',
  });
});

test('getDefaultFilters returns a new copy that cannot mutate defaults', () => {
  const filters1 = getDefaultFilters();
  const filters2 = getDefaultFilters();
  assert.deepEqual(filters1, DEFAULT_FILTERS);
  assert.notEqual(filters1, filters2);

  filters1.category = 'Agriculture';
  filters1.q = 'subsidy';
  assert.equal(filters2.category, '');
  assert.equal(DEFAULT_FILTERS.category, '');
});

test('isDefaultFilters correctly identifies default vs filtered state', () => {
  assert.equal(isDefaultFilters(getDefaultFilters()), true);
  assert.equal(isDefaultFilters({ ...DEFAULT_FILTERS, q: 'farmer' }), false);
  assert.equal(isDefaultFilters({ ...DEFAULT_FILTERS, category: 'Education' }), false);
  assert.equal(isDefaultFilters({ ...DEFAULT_FILTERS, beneficiary_group: 'student' }), false);
  assert.equal(isDefaultFilters({ ...DEFAULT_FILTERS, state: 'Karnataka' }), false);
  assert.equal(isDefaultFilters({ ...DEFAULT_FILTERS, active_only: 'false' }), false);
  assert.equal(isDefaultFilters(null), false);
});

test('buildSchemeSearchParams formats search parameters accurately', () => {
  const defaultParams = buildSchemeSearchParams(getDefaultFilters());
  assert.equal(defaultParams.get('q'), '');
  assert.equal(defaultParams.get('beneficiary_group'), '');
  assert.equal(defaultParams.get('category'), '');
  assert.equal(defaultParams.get('state'), '');
  assert.equal(defaultParams.get('active_only'), 'true');
  assert.equal(defaultParams.get('limit'), '200');

  const customParams = buildSchemeSearchParams({
    q: 'irrigation',
    beneficiary_group: 'farmer',
    category: 'Agriculture',
    state: 'Punjab',
    active_only: 'false',
  });
  assert.equal(customParams.get('q'), 'irrigation');
  assert.equal(customParams.get('beneficiary_group'), 'farmer');
  assert.equal(customParams.get('category'), 'Agriculture');
  assert.equal(customParams.get('state'), 'Punjab');
  assert.equal(customParams.get('active_only'), 'false');
  assert.equal(customParams.get('limit'), '200');
});

test('resetFiltersState resets filter fields and clears stale explore results', () => {
  const dummyState = {
    filters: {
      q: 'tractor',
      beneficiary_group: 'farmer',
      category: 'Agriculture',
      state: 'Punjab',
      active_only: 'false',
    },
    explore: [{ id: 1, name: 'Sample Scheme' }],
  };

  resetFiltersState(dummyState);

  assert.deepEqual(dummyState.filters, DEFAULT_FILTERS);
  assert.deepEqual(dummyState.explore, []);
  assert.equal(isDefaultFilters(dummyState.filters), true);
});

test('clearAuthSession resets filters and session state on logout', () => {
  const mockStorage = {
    store: { ln_token: 'jwt-token-123', explore_filters: 'stale-data', app_theme: 'dark' },
    removeItem(key) { delete this.store[key]; },
    getItem(key) { return this.store[key]; },
    setItem(key, val) { this.store[key] = val; },
  };

  const dummyState = {
    token: 'jwt-token-123',
    user: { id: 1, email: 'user@example.com' },
    profile: { full_name: 'Test User' },
    matches: [{ id: 99 }],
    filters: { q: 'pension', category: 'Social Welfare', active_only: 'true' },
    explore: [{ id: 99 }],
    active: 'explore',
    detailId: 99,
  };

  clearAuthSession(dummyState, mockStorage, mockStorage);

  assert.equal(dummyState.token, null);
  assert.equal(dummyState.user, null);
  assert.equal(dummyState.profile, null);
  assert.deepEqual(dummyState.matches, []);
  assert.deepEqual(dummyState.filters, DEFAULT_FILTERS);
  assert.deepEqual(dummyState.explore, []);
  assert.equal(dummyState.active, 'overview');
  assert.equal(dummyState.detailId, null);

  assert.equal(mockStorage.getItem('ln_token'), undefined);
  assert.equal(mockStorage.getItem('explore_filters'), undefined);
  // Unrelated storage data is preserved
  assert.equal(mockStorage.getItem('app_theme'), 'dark');
});

test('initAuthSession initializes clean default filter state on login', () => {
  const mockStorage = {
    store: {},
    removeItem(key) { delete this.store[key]; },
    getItem(key) { return this.store[key]; },
    setItem(key, val) { this.store[key] = val; },
  };

  const dummyState = {
    token: null,
    filters: { q: 'dirty-old-query', category: 'OldCategory', state: 'OldState' },
    explore: [{ id: 42 }],
    active: 'explore',
  };

  initAuthSession(dummyState, 'new-jwt-token', mockStorage);

  assert.equal(dummyState.token, 'new-jwt-token');
  assert.deepEqual(dummyState.filters, DEFAULT_FILTERS);
  assert.deepEqual(dummyState.explore, []);
  assert.equal(dummyState.active, 'overview');
  assert.equal(mockStorage.getItem('ln_token'), 'new-jwt-token');
});

test('Reset Filters action sequence resets all form controls and state', () => {
  const state = {
    filters: {
      q: 'scholarship',
      beneficiary_group: 'student',
      category: 'Education',
      state: 'Delhi',
      active_only: 'false',
    },
    explore: [{ id: 1, name: 'Filtered Scheme' }],
  };

  // Mock form elements
  const formElements = {
    q: { value: 'scholarship' },
    beneficiary_group: { value: 'student' },
    category: { value: 'Education' },
    state: { value: 'Delhi' },
    active_only: { value: 'false' },
  };

  // Simulated Reset Filters button handler
  resetFiltersState(state);
  formElements.q.value = '';
  formElements.beneficiary_group.value = '';
  formElements.category.value = '';
  formElements.state.value = '';
  formElements.active_only.value = 'true';

  assert.deepEqual(state.filters, DEFAULT_FILTERS);
  assert.deepEqual(state.explore, []);
  assert.equal(formElements.q.value, '');
  assert.equal(formElements.beneficiary_group.value, '');
  assert.equal(formElements.category.value, '');
  assert.equal(formElements.state.value, '');
  assert.equal(formElements.active_only.value, 'true');

  const refreshedParams = buildSchemeSearchParams(state.filters);
  assert.equal(refreshedParams.get('q'), '');
  assert.equal(refreshedParams.get('category'), '');
  assert.equal(refreshedParams.get('active_only'), 'true');
});
