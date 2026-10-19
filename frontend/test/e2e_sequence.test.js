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

const API_URL = 'http://localhost:8000';

test('Full 8-step sequence: filter application, logout/login isolation, and Reset Filters', async (t) => {
  // Step 1: Log in
  let loginRes;
  try {
    loginRes = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'filter_tester@example.com',
        password: 'Password123456!',
      }),
    });
  } catch (err) {
    if (t && typeof t.skip === 'function') {
      t.skip(`Backend server not running at ${API_URL}: ${err.message}`);
      return;
    }
    throw err;
  }
  assert.equal(loginRes.status, 200, 'Login must succeed with 200 OK');
  const loginData = await loginRes.json();
  assert.ok(loginData.access_token, 'Login must return an access token');

  // Simulated client session state
  const mockStorage = {
    store: {},
    removeItem(k) { delete this.store[k]; },
    getItem(k) { return this.store[k]; },
    setItem(k, v) { this.store[k] = v; },
  };

  const appState = {
    token: null,
    user: null,
    profile: null,
    matches: [],
    filters: getDefaultFilters(),
    explore: [],
    active: 'overview',
  };

  initAuthSession(appState, loginData.access_token, mockStorage);
  assert.equal(appState.token, loginData.access_token);
  assert.deepEqual(appState.filters, DEFAULT_FILTERS);

  // Step 2: Open Explore Schemes
  appState.active = 'explore';
  const defaultParams = buildSchemeSearchParams(appState.filters);
  const initialFetch = await fetch(`${API_URL}/api/schemes/search?${defaultParams}`, {
    headers: { Authorization: `Bearer ${appState.token}` },
  });
  assert.equal(initialFetch.status, 200);
  const initialData = await initialFetch.json();
  appState.explore = initialData.results || [];
  assert.equal(appState.explore.length, 125, 'Default explore schemes list must show all 125 active schemes');
  assert.equal(isDefaultFilters(appState.filters), true, 'Filters must be at initial defaults');

  // Step 3: Select a category and apply additional filters or search text
  appState.filters.category = 'Agriculture';
  appState.filters.q = 'farmer';
  assert.equal(isDefaultFilters(appState.filters), false);

  const filteredParams = buildSchemeSearchParams(appState.filters);
  const filteredFetch = await fetch(`${API_URL}/api/schemes/search?${filteredParams}`, {
    headers: { Authorization: `Bearer ${appState.token}` },
  });
  assert.equal(filteredFetch.status, 200);
  const filteredData = await filteredFetch.json();
  appState.explore = filteredData.results || [];

  // Step 4: Confirm the results are filtered
  assert.ok(appState.explore.length < 125, 'Filtered results must be a subset of total schemes');
  assert.ok(appState.explore.length > 0, 'Filtered results must match relevant schemes');
  for (const item of appState.explore) {
    assert.equal(item.category, 'Agriculture');
  }

  // Step 5: Log out
  clearAuthSession(appState, mockStorage);
  assert.equal(appState.token, null, 'Token must be cleared on logout');
  assert.deepEqual(appState.filters, DEFAULT_FILTERS, 'Filters must be reset to defaults on logout');
  assert.deepEqual(appState.explore, [], 'Explore schemes list must be cleared on logout');
  assert.equal(mockStorage.getItem('ln_token'), undefined, 'ln_token must be removed from storage');
  assert.equal(mockStorage.getItem('explore_filters'), undefined, 'Transient filter keys must not remain');

  // Step 6: Log in again
  const reLoginRes = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'filter_tester@example.com',
      password: 'Password123456!',
    }),
  });
  assert.equal(reLoginRes.status, 200);
  const reLoginData = await reLoginRes.json();
  initAuthSession(appState, reLoginData.access_token, mockStorage);

  // Step 7: Open Explore Schemes and confirm all filters are at their defaults and the full default list is displayed
  appState.active = 'explore';
  assert.deepEqual(appState.filters, DEFAULT_FILTERS, 'Filters must not persist across logout/login');
  assert.equal(isDefaultFilters(appState.filters), true);

  const reLoginParams = buildSchemeSearchParams(appState.filters);
  const reLoginFetch = await fetch(`${API_URL}/api/schemes/search?${reLoginParams}`, {
    headers: { Authorization: `Bearer ${appState.token}` },
  });
  assert.equal(reLoginFetch.status, 200);
  const reLoginExploreData = await reLoginFetch.json();
  appState.explore = reLoginExploreData.results || [];
  assert.equal(appState.explore.length, 125, 'Full default 125 schemes must be displayed after re-login');

  // Step 8: Apply filters again, click Reset Filters, and confirm everything returns to its default state
  appState.filters.category = 'Housing & Urban/Rural Development';
  appState.filters.q = 'house';
  const secondFilteredParams = buildSchemeSearchParams(appState.filters);
  const secondFilteredFetch = await fetch(`${API_URL}/api/schemes/search?${secondFilteredParams}`, {
    headers: { Authorization: `Bearer ${appState.token}` },
  });
  const secondFilteredData = await secondFilteredFetch.json();
  appState.explore = secondFilteredData.results || [];
  assert.ok(appState.explore.length < 125, 'Second filter must reduce the result set');

  // User clicks "Reset Filters"
  resetFiltersState(appState);
  assert.deepEqual(appState.filters, DEFAULT_FILTERS, 'Reset Filters button resets filters to default');
  assert.equal(isDefaultFilters(appState.filters), true);

  const resetParams = buildSchemeSearchParams(appState.filters);
  const resetFetch = await fetch(`${API_URL}/api/schemes/search?${resetParams}`, {
    headers: { Authorization: `Bearer ${appState.token}` },
  });
  assert.equal(resetFetch.status, 200);
  const resetData = await resetFetch.json();
  appState.explore = resetData.results || [];
  assert.equal(appState.explore.length, 125, 'Reset Filters refreshes the full default list (125 schemes)');
});
