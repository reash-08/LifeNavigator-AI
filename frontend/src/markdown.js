/**
 * Safe, zero-dependency Markdown parser and Scheme Response Formatter
 * Built for LifeNavigator-AI.
 *
 * Strict security rules:
 * 1. Escapes all untrusted text to prevent XSS.
 * 2. Only permits safe link protocols (http:, https:, mailto:, #).
 * 3. Never uses unsanitized innerHTML.
 * 4. Strictly preserves factual source content without inventing details.
 */

export function escapeHtml(value = '') {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

export function isSafeUrl(url = '') {
  if (!url || typeof url !== 'string') return false;
  const trimmed = url.trim();
  if (!trimmed) return false;

  // Remove whitespace and control characters to detect obfuscated protocols like "javascript :"
  const clean = trimmed.replace(/[\s\u0000-\u001f\u007f-\u009f]+/g, '');
  if (/^(javascript|data|vbscript|file):/i.test(clean)) return false;
  if (/^[a-z0-9+.-]+:/i.test(clean) && !/^(https?|mailto):/i.test(clean)) return false;

  // Allow safe relative paths and anchors
  if (trimmed.startsWith('/') || trimmed.startsWith('#')) return true;

  try {
    const parsed = new URL(trimmed);
    return ['http:', 'https:', 'mailto:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

export function sanitizeHref(url = '') {
  return isSafeUrl(url) ? escapeHtml(url.trim()) : '#';
}

/**
 * Format inline markdown tokens: bold, italic, code, markdown links, autolinks, citations.
 */
export function parseInline(rawText = '') {
  if (!rawText) return '';

  const tokens = [];
  let counter = 0;

  // 1. Markdown links: [text](url)
  let text = String(rawText).replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, href) => {
    const token = `\uFFF0LINK${counter++}\uFFF1`;
    const safe = isSafeUrl(href);
    const escapedLabel = escapeHtml(label);
    const html = safe
      ? `<a href="${escapeHtml(href.trim())}" target="_blank" rel="noopener noreferrer">${escapedLabel} ↗</a>`
      : escapedLabel;
    tokens.push({ token, html });
    return token;
  });

  // 2. Raw URLs (Autolinking): https://... or http://...
  // Exclude trailing punctuation like . , ; : ? ! from the URL
  text = text.replace(/\b(https?:\/\/[^\s<>"')]+?)([\.,;:?!]?)(?=\s|$|<|")/gi, (_match, url, punct) => {
    const token = `\uFFF0URL${counter++}\uFFF1`;
    const safe = isSafeUrl(url);
    const escaped = escapeHtml(url);
    const html = safe
      ? `<a href="${escaped}" target="_blank" rel="noopener noreferrer">${escaped} ↗</a>`
      : escaped;
    tokens.push({ token, html });
    return token + (punct || '');
  });

  // 3. Inline code: `code`
  text = text.replace(/`([^`]+)`/g, (_match, code) => {
    const token = `\uFFF0CODE${counter++}\uFFF1`;
    tokens.push({ token, html: `<code>${escapeHtml(code)}</code>` });
    return token;
  });

  // Now HTML-escape the remaining plain text
  text = escapeHtml(text);

  // 4. Bold: **text** or __text__
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>');

  // 5. Italic: *text* (single asterisk) or _text_ (single underscore)
  text = text.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, '$1<em>$2</em>$3');
  text = text.replace(/(^|[^_])_([^_]+)_([^_]|$)/g, '$1<em>$2</em>$3');

  // 6. Inline citations: [1], [2], [Source: ...]
  text = text.replace(/\[(\d+)\]/g, '<span class="citation-badge" title="Citation $1">[$1]</span>');

  // Restore tokens
  for (const { token, html } of tokens) {
    text = text.replace(token, html);
  }

  return text;
}

/**
 * Standard Markdown block renderer.
 * Converts markdown headings, paragraphs, bullet lists, ordered lists into semantic HTML.
 */
export function renderMarkdown(markdownText = '') {
  if (!markdownText || !markdownText.trim()) return '';

  const normalized = String(markdownText)
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n');

  const lines = normalized.split('\n');
  const htmlBlocks = [];
  let currentList = null; // { type: 'ul' | 'ol', items: [] }
  let currentParagraph = [];

  function flushParagraph() {
    if (currentParagraph.length > 0) {
      const pText = currentParagraph.join(' ').trim();
      if (pText) {
        htmlBlocks.push(`<p class="md-p">${parseInline(pText)}</p>`);
      }
      currentParagraph = [];
    }
  }

  function flushList() {
    if (currentList) {
      const tag = currentList.type;
      const itemsHtml = currentList.items
        .map((item) => `<li>${parseInline(item)}</li>`)
        .join('');
      htmlBlocks.push(`<${tag} class="md-list">${itemsHtml}</${tag}>`);
      currentList = null;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Empty line: flush any open paragraph or list
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    // Headings: #, ##, ###, ####
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(headingMatch[1].length + 1, 6);
      const title = headingMatch[2].trim();
      htmlBlocks.push(`<h${level} class="md-h${level}">${parseInline(title)}</h${level}>`);
      continue;
    }

    // Unordered list item: - item, * item, + item
    const ulMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    if (ulMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(ulMatch[1].trim());
      continue;
    }

    // Ordered list item: 1. item, 2. item
    const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (olMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(olMatch[1].trim());
      continue;
    }

    // Normal text line: accumulate in current paragraph
    currentParagraph.push(trimmed);
  }

  flushParagraph();
  flushList();

  return htmlBlocks.join('');
}

/**
 * Pre-processes and normalizes raw assistant response text to ensure
 * sections, scheme titles, and metadata start on clean boundaries.
 */
function normalizeAssistantText(text = '') {
  let res = String(text ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // Insert line breaks before scheme headers (# Scheme Name) if preceded by text,
  // ensuring a space follows '#' so inline strings like '#1' are never split
  res = res.replace(/([^\n#])\s*(#\s+[^#\n]+)/g, '$1\n\n$2');

  // Insert line breaks before section headers (## Overview, ## Benefits, etc.)
  res = res.replace(/([^\n#])\s*(#{2,3}\s+(?:Overview|Benefits|Eligibility(?: Criteria)?|Required Documents|How to Apply|Application Process|Official Sources|Sources)(?::|\b))/gi, '$1\n\n$2');

  // Insert line breaks before key metadata labels
  res = res.replace(/([^\n])\s*((?:Ministry \/ Department|Government Level|Application URL|Official Source Portal):\s*)/gi, '$1\n$2');

  return res;
}

/**
 * Parses and formats scheme information into clearly structured, scannable cards.
 * Recognizes sections:
 * - Overview
 * - Benefits
 * - Eligibility / Eligibility Criteria
 * - Required Documents
 * - How to Apply
 * - Official Sources
 *
 * Never invents missing sections or details; only formats what was retrieved.
 */
export function renderAssistantAnswer(rawAnswer = '', _sources = []) {
  if (!rawAnswer || !rawAnswer.trim()) {
    return '<p class="empty-answer">No detailed answer provided for this query.</p>';
  }

  const normalized = normalizeAssistantText(rawAnswer);

  // Check if the answer contains structured scheme markers (# Scheme or ## Section)
  const hasSchemeStructure = /(?:^|\n)#\s+[^#]|(?:^|\n)##\s+(?:Overview|Benefits|Eligibility|Required Documents|How to Apply|Official Sources)/i.test(normalized);

  // If there's no scheme-specific markdown structure, use the standard safe markdown renderer
  if (!hasSchemeStructure) {
    return `<div class="formatted-answer">${renderMarkdown(normalized)}</div>`;
  }

  // Parse structured scheme response
  const lines = normalized.split('\n');
  const schemes = [];
  let currentScheme = null; // { name: '', meta: [], sections: [] }
  let currentSection = null; // { title: '', badgeClass: '', content: [] }
  const preamble = [];

  function closeCurrentSection() {
    if (currentSection && currentScheme) {
      if (currentSection.content.length > 0) {
        currentScheme.sections.push(currentSection);
      }
      currentSection = null;
    }
  }

  function closeCurrentScheme() {
    closeCurrentSection();
    if (currentScheme) {
      schemes.push(currentScheme);
      currentScheme = null;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Check for major scheme title (# Scheme Name, but NOT ## or ###)
    const schemeMatch = line.match(/^#\s+([^#].*)$/);
    if (schemeMatch) {
      closeCurrentScheme();
      currentScheme = {
        name: schemeMatch[1].trim(),
        meta: [],
        sections: [],
      };
      continue;
    }

    // Check for section header (## Overview, ### Overview, ## Benefits, etc.)
    const sectionMatch = line.match(/^#{2,3}\s+(Overview|Benefits|Eligibility(?: Criteria)?|Required Documents|How to Apply|Application Process|Official Sources|Sources)(?::|\b)\s*(.*)$/i);
    if (sectionMatch) {
      if (!currentScheme) {
        currentScheme = { name: 'Scheme information', meta: [], sections: [] };
      }
      closeCurrentSection();
      const rawTitle = sectionMatch[1].trim();
      const inlineRest = sectionMatch[2].trim();

      const titleLower = rawTitle.toLowerCase();
      let badgeClass = 'badge-default';
      let cleanTitle = rawTitle;

      if (titleLower.includes('overview')) {
        badgeClass = 'badge-overview';
        cleanTitle = 'Overview';
      } else if (titleLower.includes('benefit')) {
        badgeClass = 'badge-benefits';
        cleanTitle = 'Benefits';
      } else if (titleLower.includes('eligib')) {
        badgeClass = 'badge-eligibility';
        cleanTitle = 'Eligibility Criteria';
      } else if (titleLower.includes('document')) {
        badgeClass = 'badge-docs';
        cleanTitle = 'Required Documents';
      } else if (titleLower.includes('apply') || titleLower.includes('process')) {
        badgeClass = 'badge-apply';
        cleanTitle = 'How to Apply';
      } else if (titleLower.includes('source')) {
        badgeClass = 'badge-sources';
        cleanTitle = 'Official Sources';
      }

      currentSection = {
        title: cleanTitle,
        badgeClass,
        content: inlineRest ? [inlineRest] : [],
      };
      continue;
    }

    // If we haven't hit a scheme title or section yet, treat as preamble
    if (!currentScheme) {
      preamble.push(line);
      continue;
    }

    // Check for metadata line (e.g. Ministry / Department: ..., Government Level: ...)
    const metaMatch = line.match(/^(?:[-*]\s*)?(Ministry \/ Department|Government Level|Category|State|Maximum annual income|Minimum age|Maximum age):\s*(.+)$/i);
    if (metaMatch && !currentSection) {
      currentScheme.meta.push({
        label: metaMatch[1].trim(),
        value: metaMatch[2].trim(),
      });
      continue;
    }

    // Check for Application URL or Source Portal lines inside scheme
    const appUrlMatch = line.match(/^Application URL:\s*(https?:\/\/[^\s]+)/i);
    if (appUrlMatch) {
      if (currentSection) {
        currentSection.content.push(line);
      } else {
        currentScheme.meta.push({
          label: 'Application Portal',
          value: `[Official Application Portal](${appUrlMatch[1]})`,
        });
      }
      continue;
    }

    // Content lines inside a section
    if (currentSection) {
      currentSection.content.push(line);
    } else {
      currentScheme.meta.push({ label: 'Details', value: line });
    }
  }

  closeCurrentScheme();

  // Build formatted HTML
  const out = [];

  // Preamble (e.g. "According to verified official records: ...")
  if (preamble.length > 0) {
    out.push(`<div class="answer-preamble">${renderMarkdown(preamble.join('\n\n'))}</div>`);
  }

  // Render each scheme block
  for (const scheme of schemes) {
    out.push('<article class="scheme-section-block">');

    // Header (rendered if a specific scheme name or metadata chips exist)
    const hasCustomTitle = scheme.name && scheme.name !== 'Scheme information';
    const hasMeta = scheme.meta.length > 0;
    if (hasCustomTitle || hasMeta) {
      out.push('<header class="scheme-block-head">');
      if (hasCustomTitle) {
        out.push(`<div class="scheme-block-title-row"><span class="scheme-block-icon">✳</span><h3 class="scheme-block-title">${parseInline(scheme.name)}</h3></div>`);
      }

      // Meta chips
      if (hasMeta) {
        out.push('<div class="scheme-meta-chips">');
        for (const m of scheme.meta) {
          if (m.label === 'Details') {
            out.push(`<div class="scheme-meta-lead">${parseInline(m.value)}</div>`);
          } else {
            out.push(`<span class="meta-chip"><strong>${escapeHtml(m.label)}:</strong> ${parseInline(m.value)}</span>`);
          }
        }
        out.push('</div>');
      }
      out.push('</header>');
    }

    // Sections
    if (scheme.sections.length > 0) {
      out.push('<div class="scheme-sections-container">');
      for (const sec of scheme.sections) {
        out.push(`<section class="scheme-card-section ${sec.badgeClass}-container">`);
        out.push('<div class="section-badge-header">');
        out.push(`<span class="section-badge ${sec.badgeClass}">${sec.title}</span>`);
        out.push('</div>');

        const joinedContent = sec.content.join('\n');
        out.push(`<div class="section-body">${renderMarkdown(joinedContent)}</div>`);
        out.push('</section>');
      }
      out.push('</div>');
    }

    out.push('</article>');
  }

  return `<div class="formatted-answer">${out.join('')}</div>`;
}
