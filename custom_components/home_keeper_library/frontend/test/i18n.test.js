import { afterEach, describe, expect, it } from 'vitest';
import { formatAgo, formatDate, formatMoney, formatNumber, getLanguage, setLanguage, t, tn } from '../src/i18n.ts';
import { DEFAULT_LOCALE, LOCALES } from '../src/locales/index.ts';

// Behaviour of the i18n module. The translation gates (parity, leaks, key usage)
// are in `i18n-parity.test.js`, which the mutation run skips.

afterEach(() => setLanguage(DEFAULT_LOCALE));

/** Run *body* with extra keys in a locale table, then remove them. */
function withKeys(keys, body, locale = DEFAULT_LOCALE) {
  const table = LOCALES[locale];
  try {
    Object.assign(table, keys);
    body();
  } finally {
    for (const key of Object.keys(keys)) delete table[key];
  }
}

describe('setLanguage', () => {
  it('finds an exact tag, also a regional one', () => {
    setLanguage('pt-BR');
    expect(getLanguage()).toBe('pt-BR');
    setLanguage('zh-hans');
    expect(getLanguage()).toBe('zh-Hans');
    setLanguage('zh_Hans');
    expect(getLanguage()).toBe('zh-Hans');
    setLanguage('DE');
    expect(getLanguage()).toBe('de');
  });
  it('falls back to the base language', () => {
    setLanguage('de-AT');
    expect(getLanguage()).toBe('de');
    setLanguage('pt-PT');
    expect(getLanguage()).toBe('pt-BR');
    setLanguage('zh-Hant');
    expect(getLanguage()).toBe('zh-Hans');
  });
  it('falls back to English for an unknown or empty language', () => {
    setLanguage('xx-YY');
    expect(getLanguage()).toBe('en');
    setLanguage('de');
    setLanguage('');
    expect(getLanguage()).toBe('en');
    setLanguage('de');
    setLanguage(undefined);
    expect(getLanguage()).toBe('en');
  });
  it('uses the table of the language', () => {
    withKeys({ 'tmp.x': 'Hallo' }, () => {
      setLanguage('de');
      expect(t('tmp.x')).toBe('Hallo');
    }, 'de');
  });
});

describe('t', () => {
  it('fills tokens and keeps unknown tokens', () => {
    expect(t('book.page_of', { page: 3, pages: 10 })).toBe('Page 3 of 10');
    expect(t('book.page_of', { page: 0 })).toBe('Page 0 of {pages}');
    expect(t('book.page_of', { page: null, pages: '' })).toBe('Page {page} of ');
    expect(t('book.page_of')).toBe('Page {page} of {pages}');
  });
  it('falls back to English, then to the key', () => {
    withKeys({ 'tmp.en': 'English only' }, () => {
      setLanguage('fr');
      expect(t('tmp.en')).toBe('English only');
    });
    expect(t('no.such.key')).toBe('no.such.key');
  });
});

describe('tn', () => {
  it('picks the English plural', () => {
    expect(tn('count.books', 1)).toBe('1 book');
    expect(tn('count.books', 0)).toBe('0 books');
    expect(tn('count.books', 7)).toBe('7 books');
    expect(tn('count.books', 7, { n: 'seven' })).toBe('seven books');
  });
  it('picks few and many in Polish', () => {
    withKeys({ 'tmp.p.one': '{n} A', 'tmp.p.few': '{n} B', 'tmp.p.many': '{n} C', 'tmp.p.other': '{n} D' }, () => {
      setLanguage('pl');
      expect(tn('tmp.p', 1)).toBe('1 A');
      expect(tn('tmp.p', 3)).toBe('3 B');
      expect(tn('tmp.p', 5)).toBe('5 C');
      expect(tn('tmp.p', 1.5)).toBe('1.5 D');
    }, 'pl');
  });
  it('falls back in order: category, other, English category, English other, key', () => {
    withKeys({ 'tmp.f.other': '{n} local' }, () => {
      setLanguage('de');
      expect(tn('tmp.f', 1)).toBe('1 local');
    }, 'de');
    withKeys({ 'tmp.g.one': '{n} en one', 'tmp.g.other': '{n} en other' }, () => {
      setLanguage('de');
      expect(tn('tmp.g', 1)).toBe('1 en one');
      expect(tn('tmp.g', 2)).toBe('2 en other');
    });
    expect(tn('tmp.none', 2)).toBe('tmp.none');
  });
});

describe('formatters', () => {
  it('formats a date in the language', () => {
    expect(formatDate('2026-03-02')).toBe('Mar 2, 2026');
    expect(formatDate('2026-03-02', false)).toBe('Mar 2');
    expect(formatDate('2026-03-02T12:00:00')).toBe('Mar 2, 2026');
    setLanguage('de');
    expect(formatDate('2026-03-02')).toBe('2. März 2026');
    expect(formatDate('')).toBe('');
    expect(formatDate(null)).toBe('');
    expect(formatDate('nope')).toBe('');
  });
  it('formats money, with a fallback for a bad currency', () => {
    expect(formatMoney(7.99, 'USD')).toBe('$7.99');
    expect(formatMoney(0, 'USD')).toBe('$0.00');
    expect(formatMoney(null, 'USD')).toBe('');
    expect(formatMoney(undefined, 'USD')).toBe('');
    expect(formatMoney(5, 'not a code')).toBe('5 not a code');
    setLanguage('de');
    expect(formatMoney(7.5, 'EUR')).toBe('7,50 €');
  });
  it('formats numbers and days ago', () => {
    expect(formatNumber(3890)).toBe('3,890');
    expect(formatAgo(0)).toBe('today');
    expect(formatAgo(1)).toBe('yesterday');
    expect(formatAgo(3)).toBe('3 days ago');
    setLanguage('de');
    expect(formatNumber(3890)).toBe('3.890');
  });
});
