import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DEFAULT_LOCALE, LOCALES } from '../src/locales/index.ts';

// Translation gates: key parity, placeholder parity, untranslated leaks, plural
// completeness and key usage. Key usage reads `src/*.ts` off disk, so this file is
// a `*-parity` test that the mutation run skips (see vitest.stryker.config.js).

const EN = LOCALES[DEFAULT_LOCALE];
const OTHER = Object.keys(LOCALES).filter((l) => l !== DEFAULT_LOCALE);
const PLURAL = /^(.*)\.(zero|one|two|few|many|other)$/;

// Values that are the same as English by design: the product name, file format
// names, the "ISBN" code and a bare "{name}: {list}" pair. Keep this list short.
const IDENTICAL = new Set(['card.name', 'scan.isbn', 'import.source_goodreads', 'import.source_storygraph', 'wishlist.list_for']);

// Words that are the same as English in one language, reviewed one by one. "Person",
// "Format", "Status", "Version", "Export" and "Optional" are the native words in the
// Germanic languages listed. French uses "Page", "Format", "Source" and "Sections".
// Italian uses "Area". Dutch and Danish use "Paperback", Polish uses "Audiobook",
// Danish uses "Note" and the verb "Scan".
const COGNATES = {
  ca: ['copy.format'],
  cs: ['settings.export'],
  da: ['action.scan', 'common.person', 'common.version', 'copy.format', 'copy.note', 'filter.status_label', 'format.kind_paperback', 'scan.scan_shelf'],
  de: ['common.optional', 'common.person', 'common.version', 'copy.format', 'dialog.name', 'filter.status_label', 'import.source_library', 'settings.export'],
  fr: ['book.page', 'book.page_n', 'book.pages.one', 'book.pages.other', 'common.version', 'copy.format', 'editor.sections', 'import.source'],
  it: ['dialog.area', 'shelves.area'],
  nb: ['common.person', 'copy.format', 'filter.status_label'],
  nl: ['filter.status_label', 'format.kind_paperback'],
  pl: ['copy.format', 'format.kind_audiobook'],
  sv: ['common.person', 'common.version', 'copy.format', 'filter.status_label', 'settings.export'],
};

const tokens = (s) => [...new Set(String(s).match(/\{\w+\}/g) ?? [])].sort();

describe.each(OTHER)('locale %s', (lang) => {
  const table = LOCALES[lang];

  it('has every English key and no extra key except plural forms', () => {
    expect(Object.keys(EN).filter((k) => !(k in table))).toEqual([]);
    const extra = Object.keys(table).filter((k) => !(k in EN));
    const bad = extra.filter((k) => {
      const m = k.match(PLURAL);
      return !m || EN[`${m[1]}.other`] === undefined;
    });
    expect(bad).toEqual([]);
  });

  it('keeps the placeholder tokens', () => {
    for (const key of Object.keys(table)) {
      const m = key.match(PLURAL);
      const source = EN[key] ?? (m ? EN[`${m[1]}.other`] : undefined);
      expect(tokens(table[key]), `${lang} ${key}`).toEqual(tokens(source));
    }
  });

  it('has no value that is the same as English', () => {
    const allowed = new Set([...IDENTICAL, ...(COGNATES[lang] ?? [])]);
    const leaks = Object.keys(EN).filter((k) => table[k] === EN[k] && !allowed.has(k));
    expect(leaks).toEqual([]);
  });

  it('has every plural category that the language uses', () => {
    const cats = new Intl.PluralRules(lang).resolvedOptions().pluralCategories;
    const bases = new Set(Object.keys(EN).map((k) => k.match(PLURAL)?.[1]).filter(Boolean));
    const missing = [];
    for (const base of bases) for (const c of cats) if (table[`${base}.${c}`] === undefined) missing.push(`${base}.${c}`);
    expect(missing).toEqual([]);
  });
});

describe('key usage', () => {
  const rel = 'custom_components/home_keeper_library/frontend/src';
  const dir = existsSync(resolve(process.cwd(), rel)) ? resolve(process.cwd(), rel) : resolve(process.cwd(), 'src');
  const SRC = readdirSync(dir)
    .filter((f) => f.endsWith('.ts'))
    .map((f) => readFileSync(`${dir}/${f}`, 'utf8'))
    .join('\n');
  const literal = (fn) => [...SRC.matchAll(new RegExp(`\\b${fn}\\(\\s*'([^']+)'`, 'g'))].map((m) => m[1]);
  const T_KEYS = new Set(literal('t'));
  const TN_KEYS = new Set(literal('tn'));
  // A dynamic key: t(`prefix.${x}`). Each key with that prefix counts as used.
  const DYN = [...new Set([...SRC.matchAll(/\btn?\(\s*`([^`$]*)\$\{/g)].map((m) => m[1]))];

  it('every literal t() key is in English', () => {
    expect([...T_KEYS].filter((k) => EN[k] === undefined)).toEqual([]);
  });

  it('every literal tn() key has an English .one and .other', () => {
    expect([...TN_KEYS].filter((k) => EN[`${k}.other`] === undefined || EN[`${k}.one`] === undefined)).toEqual([]);
  });

  it('every English key is used', () => {
    const used = (key) => {
      const base = key.match(PLURAL)?.[1];
      if (T_KEYS.has(key) || (base && TN_KEYS.has(base))) return true;
      return DYN.some((p) => p.includes('.') && key.startsWith(p));
    };
    expect(Object.keys(EN).filter((k) => !used(k))).toEqual([]);
  });

  it('every dynamic prefix has keys', () => {
    for (const p of DYN.filter((x) => x.includes('.'))) {
      expect(Object.keys(EN).some((k) => k.startsWith(p)), p).toBe(true);
    }
  });
});
