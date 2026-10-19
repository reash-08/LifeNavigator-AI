import test from 'node:test';
import assert from 'node:assert/strict';

// Helper mirroring matchStatus logic in frontend/src/main.js
const statusInfo = (status) => ({
  eligible: ['Eligible', 'status-good'],
  not_eligible: ['Not eligible', 'status-no'],
  not_confirmed: ['Needs more details', 'status-warn'],
  profile_required: ['Complete your profile', 'status-warn'],
  not_evaluated: ['Not assessed', 'status-neutral'],
}[status] || ['Not assessed', 'status-neutral']);

function matchStatus(item) {
  const unknown = item.eligibility_verification_status !== 'verified' || (item.reasons || []).some((reason) => /missing|not confirmed|not verified|not registered|no verified eligibility/i.test(reason));
  return statusInfo(unknown ? 'not_confirmed' : item.eligible ? 'eligible' : 'not_eligible');
}

test('unverified schemes never return affirmative eligibility badge', () => {
  const unverifiedItem = {
    id: 11,
    name: 'PM-KISAN',
    eligible: true, // even if backend had eligible: true accidentally
    eligibility_verification_status: 'unverified',
    reasons: ['Eligibility criteria have not been verified; check the official source'],
  };
  const [label, cssClass] = matchStatus(unverifiedItem);
  assert.equal(label, 'Needs more details');
  assert.equal(cssClass, 'status-warn');
  assert.notEqual(label, 'Eligible');
});

test('reasons containing missing attributes map to Needs more details', () => {
  const itemWithMissing = {
    id: 11,
    name: 'PM-KISAN',
    eligible: false,
    eligibility_verification_status: 'verified',
    reasons: ['land_ownership is missing'],
  };
  const [label, cssClass] = matchStatus(itemWithMissing);
  assert.equal(label, 'Needs more details');
  assert.equal(cssClass, 'status-warn');
});

test('verified schemes with met criteria return Eligible badge', () => {
  const verifiedItem = {
    id: 11,
    name: 'PM-KISAN',
    eligible: true,
    eligibility_verification_status: 'verified',
    reasons: ['Rules matched (AND): is_farmer equals true, land_ownership equals true'],
  };
  const [label, cssClass] = matchStatus(verifiedItem);
  assert.equal(label, 'Eligible');
  assert.equal(cssClass, 'status-good');
});

test('verified schemes with unmet criteria return Not eligible badge', () => {
  const verifiedItem = {
    id: 19,
    name: 'PMAY-U 2.0',
    eligible: false,
    eligibility_verification_status: 'verified',
    reasons: ['Rules did not match (AND): rural_or_urban equals urban, owns_house equals false'],
  };
  const [label, cssClass] = matchStatus(verifiedItem);
  assert.equal(label, 'Not eligible');
  assert.equal(cssClass, 'status-no');
});
