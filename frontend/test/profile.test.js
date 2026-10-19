import test from 'node:test';
import assert from 'node:assert/strict';
import { buildProfilePayload } from '../src/profile.js';

const fields = [['age', 'Age', 'number'], ['is_farmer', 'Farmer', 'boolean'], ['state', 'State', 'text']];

test('profile values become the types expected by the API', () => {
  assert.deepEqual(buildProfilePayload({ age: '35', is_farmer: 'true', state: 'Karnataka' }, fields), {
    age: 35, is_farmer: true, state: 'Karnataka',
  });
});

test('blank optional profile values are sent as null', () => {
  assert.deepEqual(buildProfilePayload({ age: '35', is_farmer: '', state: 'Karnataka' }, fields), {
    age: 35, is_farmer: null, state: 'Karnataka',
  });
});

test('false remains distinct from an unspecified boolean', () => {
  assert.deepEqual(buildProfilePayload({ is_farmer: 'false' }, fields), { is_farmer: false });
});
