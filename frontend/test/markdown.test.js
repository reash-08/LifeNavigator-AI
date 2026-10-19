import test from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml,
  isSafeUrl,
  sanitizeHref,
  parseInline,
  renderMarkdown,
  renderAssistantAnswer,
} from '../src/markdown.js';

test('escapeHtml safely converts HTML entities and disallows raw tags', () => {
  assert.equal(escapeHtml('<script>alert("xss")</script>'), '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  assert.equal(escapeHtml('Tom & Jerry "quotes" and \'single\''), 'Tom &amp; Jerry &quot;quotes&quot; and &#39;single&#39;');
  assert.equal(escapeHtml(''), '');
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
});

test('isSafeUrl allows http, https, mailto, and relative paths but blocks dangerous protocols', () => {
  assert.equal(isSafeUrl('https://pmkisan.gov.in'), true);
  assert.equal(isSafeUrl('http://india.gov.in/schemes'), true);
  assert.equal(isSafeUrl('mailto:support@lifenavigator.in'), true);
  assert.equal(isSafeUrl('/schemes/1'), true);
  assert.equal(isSafeUrl('#benefits'), true);

  // Dangerous protocols must be blocked
  assert.equal(isSafeUrl('javascript:alert(1)'), false);
  assert.equal(isSafeUrl('JAVASCRIPT:alert(1)'), false);
  assert.equal(isSafeUrl('javascript :alert(1)'), false);
  assert.equal(isSafeUrl('data:text/html,<script>alert(1)</script>'), false);
  assert.equal(isSafeUrl('vbscript:msgbox("hi")'), false);
  assert.equal(isSafeUrl('file:///C:/Windows/win.ini'), false);
  assert.equal(isSafeUrl(''), false);
  assert.equal(isSafeUrl('   '), false);
});

test('sanitizeHref returns safe URL or fallback anchor', () => {
  assert.equal(sanitizeHref('https://pmkisan.gov.in'), 'https://pmkisan.gov.in');
  assert.equal(sanitizeHref('javascript:evil()'), '#');
  assert.equal(sanitizeHref(''), '#');
});

test('parseInline correctly formats bold, italic, code, links, and autolinks', () => {
  // Bold
  assert.ok(parseInline('**PM-KISAN**').includes('<strong>PM-KISAN</strong>'));
  assert.ok(parseInline('__Important__').includes('<strong>Important</strong>'));

  // Italic
  assert.ok(parseInline('*income support*').includes('<em>income support</em>'));

  // Code
  assert.ok(parseInline('`npm run dev`').includes('<code>npm run dev</code>'));

  // Safe markdown link
  const linkResult = parseInline('[Official Portal](https://pmkisan.gov.in)');
  assert.ok(linkResult.includes('<a href="https://pmkisan.gov.in" target="_blank" rel="noopener noreferrer">Official Portal ↗</a>'));

  // Unsafe markdown link stripped
  const unsafeResult = parseInline('[Click Here](javascript:alert(1))');
  assert.ok(!unsafeResult.includes('href="javascript:'));
  assert.ok(!unsafeResult.includes('<a'));
  assert.ok(unsafeResult.includes('Click Here'));

  // Raw autolink
  const autoResult = parseInline('Visit https://pmkisan.gov.in for updates.');
  assert.ok(autoResult.includes('<a href="https://pmkisan.gov.in" target="_blank" rel="noopener noreferrer">https://pmkisan.gov.in ↗</a>'));

  // XSS prevention in inline text
  const xssResult = parseInline('**<img src=x onerror=alert(1)>**');
  assert.ok(xssResult.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(!xssResult.includes('<img'));
});

test('renderMarkdown converts headings, bullet lists, ordered lists, and paragraphs', () => {
  const md = `
# Main Title
## Section Two
### Sub Section

Here is a paragraph with **bold** text and [safe link](https://example.com).

- First bullet
- Second bullet
- Third bullet

1. Number one
2. Number two

Another closing paragraph.
`;

  const html = renderMarkdown(md);
  assert.ok(html.includes('<h2 class="md-h2">Main Title</h2>'));
  assert.ok(html.includes('<h3 class="md-h3">Section Two</h3>'));
  assert.ok(html.includes('<h4 class="md-h4">Sub Section</h4>'));
  assert.ok(html.includes('<p class="md-p">Here is a paragraph'));
  assert.ok(html.includes('<strong>bold</strong>'));
  assert.ok(html.includes('<ul class="md-list"><li>First bullet</li><li>Second bullet</li><li>Third bullet</li></ul>'));
  assert.ok(html.includes('<ol class="md-list"><li>Number one</li><li>Number two</li></ol>'));
  assert.ok(html.includes('<p class="md-p">Another closing paragraph.</p>'));
});

test('renderAssistantAnswer formats structured scheme responses into clear scannable sections', () => {
  const answer = `
According to verified official records: PM-KISAN provides income support.

# Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)
Ministry / Department: Ministry of Agriculture & Farmers Welfare
Government Level: central | State: All India Category: Agriculture

## Overview
Flagship central sector scheme providing income support to all landholding farmer families.

## Benefits
Financial benefit of Rs 6,000 per year payable in three equal installments of Rs 2,000 every four months.

## Eligibility Criteria
- Beneficiary Groups: farmer families, small and marginal farmers
- Ownership: cultivable landholding in revenue records

## Required Documents
Aadhaar card, land ownership records, bank account details.

## How to Apply
Farmers can apply through farmers corner at https://pmkisan.gov.in or Common Service Centres.

Application URL: https://pmkisan.gov.in/
Official Source Portal: https://agricoop.nic.in/
`;

  const html = renderAssistantAnswer(answer);

  // Check scheme block title
  assert.ok(html.includes('Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)'));
  assert.ok(html.includes('scheme-block-title'));

  // Check metadata chips
  assert.ok(html.includes('Ministry / Department:'));
  assert.ok(html.includes('Government Level:'));

  // Check standard sections
  assert.ok(html.includes('badge-overview'));
  assert.ok(html.includes('Overview'));
  assert.ok(html.includes('Flagship central sector scheme'));

  assert.ok(html.includes('badge-benefits'));
  assert.ok(html.includes('Benefits'));
  assert.ok(html.includes('Financial benefit of Rs 6,000'));

  assert.ok(html.includes('badge-eligibility'));
  assert.ok(html.includes('Eligibility Criteria'));

  assert.ok(html.includes('badge-docs'));
  assert.ok(html.includes('Required Documents'));
  assert.ok(html.includes('Aadhaar card'));

  assert.ok(html.includes('badge-apply'));
  assert.ok(html.includes('How to Apply'));

  // Check safe clickable links
  assert.ok(html.includes('href="https://pmkisan.gov.in"'));
  assert.ok(html.includes('href="https://agricoop.nic.in/"'));
});

test('renderAssistantAnswer handles unstructured general answers gracefully', () => {
  const general = `
Here is general information about welfare schemes:

* Many schemes offer financial assistance.
* Some require proof of income or caste certificates.

Please check your state guidelines at https://india.gov.in.
`;

  const html = renderAssistantAnswer(general);
  assert.ok(html.includes('<ul class="md-list">'));
  assert.ok(html.includes('Many schemes offer financial assistance.'));
  assert.ok(html.includes('<a href="https://india.gov.in" target="_blank" rel="noopener noreferrer">https://india.gov.in ↗</a>'));
});

test('renderAssistantAnswer does not invent missing sections', () => {
  const partialAnswer = `
# Simple Scheme
## Overview
Just an overview of this scheme.

## Benefits
Some basic benefits.
`;

  const html = renderAssistantAnswer(partialAnswer);
  assert.ok(html.includes('badge-overview'));
  assert.ok(html.includes('badge-benefits'));
  // Must NOT invent Required Documents or How to Apply if not in source
  assert.ok(!html.includes('badge-docs'));
  assert.ok(!html.includes('badge-apply'));
});

test('renderAssistantAnswer handles empty, null, or whitespace-only answers', () => {
  assert.ok(renderAssistantAnswer('').includes('No detailed answer'));
  assert.ok(renderAssistantAnswer(null).includes('No detailed answer'));
  assert.ok(renderAssistantAnswer('   ').includes('No detailed answer'));
});

test('renderAssistantAnswer handles short conversational answers cleanly without scheme blocks', () => {
  const shortAnswer = 'Yes, you may qualify if your annual family income is below Rs 2,50,000. Please verify with your local district office.';
  const html = renderAssistantAnswer(shortAnswer);
  assert.ok(html.includes('<p class="md-p">Yes, you may qualify'));
  assert.ok(!html.includes('scheme-section-block'));
  assert.ok(!html.includes('badge-overview'));
});

test('renderAssistantAnswer handles long response with multiple sections cleanly', () => {
  const multiSection = `
# Comprehensive Welfare Support Scheme
* Ministry / Department: Ministry of Social Justice and Empowerment
* Government Level: Central Government
* Category: Education & Financial Assistance

## Overview
A comprehensive national initiative to provide holistic educational and economic support.

## Benefits
* Annual scholarship of Rs 12,000 for day scholars.
* Annual scholarship of Rs 24,000 for hostel residents.
* Free digital study material access.

## Eligibility
* Students enrolled in recognized government colleges.
* Family annual income must be below Rs 3,00,000.
* Minimum 60% marks in higher secondary examinations.

## Required Documents
* Income certificate issued by competent revenue authority.
* Recent educational mark sheets and college admission receipt.
* Aadhaar card linked with active bank account.

## How to Apply
1. Register on the official national portal.
2. Complete e-KYC verification using Aadhaar OTP.
3. Submit application before the designated deadline.

## Official Sources
* Official scholarship portal: https://scholarships.gov.in
`;

  const html = renderAssistantAnswer(multiSection);
  assert.ok(html.includes('Comprehensive Welfare Support Scheme'));
  assert.ok(html.includes('Ministry of Social Justice and Empowerment'));
  assert.ok(html.includes('badge-overview'));
  assert.ok(html.includes('badge-benefits'));
  assert.ok(html.includes('badge-eligibility'));
  assert.ok(html.includes('badge-docs'));
  assert.ok(html.includes('badge-apply'));
  assert.ok(html.includes('badge-sources'));
  assert.ok(html.includes('https://scholarships.gov.in'));
  assert.ok(!html.includes('##'));
  assert.ok(!html.includes('**'));
});

test('renderAssistantAnswer supports bulleted metadata chips and long titles without splitting inline hashes', () => {
  const withBullets = `
# Pradhan Mantri Awas Yojana - Housing for All (Urban / Rural Unified Mission)
- Ministry / Department: Ministry of Housing and Urban Affairs
- Government Level: Central
- State: All India

## Overview
Provides central assistance to urban local bodies and rural agencies for providing pucca houses to eligible families. See Section #1 guidelines.
`;

  const html = renderAssistantAnswer(withBullets);
  assert.ok(html.includes('Pradhan Mantri Awas Yojana - Housing for All (Urban / Rural Unified Mission)'));
  assert.ok(html.includes('Ministry of Housing and Urban Affairs'));
  assert.ok(html.includes('badge-overview'));
  // Ensure inline hashtag like #1 is NOT treated as a broken header
  assert.ok(html.includes('Section #1 guidelines'));
  assert.ok(!html.includes('## Overview'));
});
