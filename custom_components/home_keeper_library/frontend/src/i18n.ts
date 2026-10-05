import { DEFAULT_LOCALE, LOCALES } from './locales';

/**
 * Small i18n module for the tab and the card. The locale tables are in the
 * bundle (see `locales/index.ts`), so there is no fetch at run time. A lookup
 * falls back to English for each key, and then to the key itself.
 */

type Table = Record<string, string>;

const fallback: Table = LOCALES[DEFAULT_LOCALE];
let current: Table = fallback;
let currentLang: string = DEFAULT_LOCALE;
let plural: Intl.PluralRules = new Intl.PluralRules(DEFAULT_LOCALE);

/** Find the table for a Home Assistant language code ("en-GB", "pt-BR", "zh-Hans"). */
function resolve(lang: string): { table: Table; tag: string } {
  const lc = lang.toLowerCase().replace('_', '-');
  // An exact match first, so "pt-BR" and "zh-Hans" find their own tables.
  for (const key of Object.keys(LOCALES)) {
    if (key.toLowerCase() === lc) return { table: LOCALES[key], tag: key };
  }
  // Then the base language: "en-GB" finds "en", "pt-PT" finds "pt-BR".
  const base = lc.split('-')[0];
  for (const key of Object.keys(LOCALES)) {
    if (key.toLowerCase().split('-')[0] === base) return { table: LOCALES[key], tag: key };
  }
  return { table: fallback, tag: DEFAULT_LOCALE };
}

/** Set the active locale. Safe to call on each `hass` update. */
export function setLanguage(lang?: string): void {
  const { table, tag } = resolve(lang || DEFAULT_LOCALE);
  current = table;
  currentLang = tag;
  plural = new Intl.PluralRules(tag);
}

/** The active locale tag. */
export function getLanguage(): string {
  return currentLang;
}

function interpolate(tmpl: string, params?: Record<string, string | number>): string {
  if (!params) return tmpl;
  return tmpl.replace(/\{(\w+)\}/g, (_m, name: string) =>
    params[name] != null ? String(params[name]) : `{${name}}`,
  );
}

/** Translate a key and fill its `{param}` tokens. */
export function t(key: string, params?: Record<string, string | number>): string {
  const tmpl = current[key] ?? fallback[key] ?? key;
  return interpolate(tmpl, params);
}

/**
 * Translate a key with a count. The locale plural rules pick
 * `"<key>.<category>"`, with `"<key>.other"` as the fallback. The template can
 * use the count as `{n}`.
 */
export function tn(key: string, n: number, params?: Record<string, string | number>): string {
  const cat = plural.select(n);
  const tmpl =
    current[`${key}.${cat}`] ??
    current[`${key}.other`] ??
    fallback[`${key}.${cat}`] ??
    fallback[`${key}.other`] ??
    key;
  return interpolate(tmpl, { n, ...params });
}

/** A date (YYYY-MM-DD or ISO) in the active locale, or '' for a bad value. */
export function formatDate(value: string | null | undefined, withYear = true): string {
  if (!value) return '';
  const d = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(d.getTime())) return '';
  const opts: Intl.DateTimeFormatOptions = withYear
    ? { year: 'numeric', month: 'short', day: 'numeric' }
    : { month: 'short', day: 'numeric' };
  return d.toLocaleDateString(currentLang, opts);
}

/** An amount of money in the active locale, or '' for no amount. */
export function formatMoney(value: number | null | undefined, currency: string): string {
  if (value == null) return '';
  try {
    return new Intl.NumberFormat(currentLang, { style: 'currency', currency }).format(value);
  } catch {
    return `${value} ${currency}`;
  }
}

/** A number in the active locale. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat(currentLang).format(value);
}

/** "3 days ago", "yesterday" and so on, in the active locale. */
export function formatAgo(days: number): string {
  return new Intl.RelativeTimeFormat(currentLang, { numeric: 'auto' }).format(-days, 'day');
}
