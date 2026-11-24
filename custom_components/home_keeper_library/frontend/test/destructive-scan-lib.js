// The scanner behind `destructive-scan-parity.test.js`.
//
// It reads the TypeScript of the tab and the card as text and finds each place that
// starts a command which deletes, removes, disconnects or replaces data. A command is
// a string such as `'delete_book'`, or a call of a function that is destructive by
// effect. A place is safe when it sits inside a `_confirm(...)` or `mountConfirm(...)`
// call, so the confirm button runs it, or inside another destructive function, whose
// own callers are checked in turn, or has an entry in the allowlist with a reason.
//
// It is a text scan, not a type check. It cannot see a command that goes through a
// variable. Its job is the common slip: a new delete button that runs at once.

/** A command that deletes, removes, disconnects or replaces data. */
export const DESTRUCTIVE_COMMAND = /^(delete|remove|disconnect|clear|reset|purge|restore|import)_/;

/** Destructive by effect, not by name. Each is checked as a call. */
export const EXTRA_NAMES = ['_removeMiss', '_runImport', 'importCsv'];

/** Files that only declare types, and the file that defines the commands. */
export const SKIP = ['api.ts', 'types.ts', 'tab-types.ts', 'global.d.ts'];

/** The calls whose arguments run only after a "yes". */
export const GUARDS = ['_confirm', 'mountConfirm'];

const KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'new']);

/**
 * Replace comments and the inside of strings, templates and regular expressions with
 * spaces, and keep every other character and every newline, so an offset in the result
 * is an offset in the source.
 */
export function blank(src) {
  const out = src.split('');
  let i = 0;
  const wipe = (from, to) => {
    for (let k = from; k < to; k += 1) if (out[k] !== '\n') out[k] = ' ';
  };
  let prev = '';
  while (i < src.length) {
    const c = src[i];
    const d = src[i + 1];
    if (c === '/' && d === '/') {
      const end = src.indexOf('\n', i);
      const to = end < 0 ? src.length : end;
      wipe(i, to);
      i = to;
    } else if (c === '/' && d === '*') {
      const end = src.indexOf('*/', i + 2);
      const to = end < 0 ? src.length : end + 2;
      wipe(i, to);
      i = to;
    } else if (c === "'" || c === '"' || c === '`') {
      let k = i + 1;
      while (k < src.length && src[k] !== c) k += src[k] === '\\' ? 2 : 1;
      wipe(i + 1, k);
      i = k + 1;
      prev = c;
    } else if (c === '/' && /[(,=:[!&|?{};]|^$/.test(prev)) {
      // A regular expression literal: skip to the closing slash, outside a class.
      let k = i + 1;
      let inClass = false;
      while (k < src.length && src[k] !== '\n') {
        if (src[k] === '\\') k += 2;
        else {
          if (src[k] === '[') inClass = true;
          else if (src[k] === ']') inClass = false;
          else if (src[k] === '/' && !inClass) break;
          k += 1;
        }
      }
      wipe(i + 1, k);
      i = k + 1;
      prev = '/';
    } else {
      if (!/\s/.test(c)) prev = c;
      i += 1;
    }
  }
  return out.join('');
}

/** The index of the bracket that closes the one at *open*, or -1. */
export function matching(code, open) {
  const pairs = { '(': ')', '{': '}', '[': ']' };
  const stack = [];
  for (let i = open; i < code.length; i += 1) {
    const c = code[i];
    if (pairs[c]) stack.push(pairs[c]);
    else if (c === ')' || c === '}' || c === ']') {
      if (stack.pop() !== c) return -1;
      if (!stack.length) return i;
    }
  }
  return -1;
}

/** The named functions of a file, each with the range of its body. */
export function functionsOf(code) {
  const found = [];
  const add = (name, from) => {
    const brace = code.indexOf('{', from);
    if (brace < 0 || KEYWORDS.has(name)) return;
    const end = matching(code, brace);
    if (end > brace) found.push({ name, start: brace, end });
  };
  let m;
  const decl = /\bfunction\s+(\w+)\s*(?:<[^>]*>)?\s*\(/g;
  while ((m = decl.exec(code))) {
    const close = matching(code, m.index + m[0].length - 1);
    if (close > 0) add(m[1], close);
  }
  const method = /(?:^|[\n;{}]\s*)(?:(?:export|private|public|protected|static|async)\s+)*(\w+)\s*(?:<[^>]*>)?\s*\(/g;
  while ((m = method.exec(code))) {
    if (KEYWORDS.has(m[1])) continue;
    const open = m.index + m[0].length - 1;
    const close = matching(code, open);
    if (close < 0) continue;
    const after = code.slice(close + 1).match(/^\s*(?::\s*[^{;=]+?)?\s*\{/);
    if (after) add(m[1], close);
  }
  const arrow = /\b(?:const|let)\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?\(/g;
  while ((m = arrow.exec(code))) {
    const open = m.index + m[0].length - 1;
    const close = matching(code, open);
    if (close < 0) continue;
    const after = code.slice(close + 1).match(/^\s*(?::\s*[^=]+?)?\s*=>\s*\{/);
    if (after) add(m[1], close);
  }
  return found;
}

/** The argument ranges of every guard call in the file. */
export function guardRanges(code) {
  const ranges = [];
  for (const name of GUARDS) {
    const re = new RegExp(`\\b${name}\\s*\\(`, 'g');
    let m;
    while ((m = re.exec(code))) {
      const open = m.index + m[0].length - 1;
      const close = matching(code, open);
      if (close > open) ranges.push([open, close]);
    }
  }
  return ranges;
}

/** Whether a function of this name is destructive by effect. */
export const isDestructiveFunction = (name) => EXTRA_NAMES.includes(name);

/** Every place in *source* that starts a destructive command: `{ at, what }`. */
export function findings(source, code) {
  const out = [];
  // A command string. The blanked copy keeps the quotes, so a string in a comment is skipped.
  const lit = /(['"`])([a-z]+(?:_[a-z]+)+)\1/g;
  let m;
  while ((m = lit.exec(source))) {
    if (code[m.index] !== m[1]) continue;
    if (DESTRUCTIVE_COMMAND.test(m[2])) out.push({ at: m.index, what: m[2] });
  }
  // A call of a function that is destructive by effect.
  for (const name of EXTRA_NAMES) {
    const call = new RegExp(`\\b${name}\\s*\\(`, 'g');
    while ((m = call.exec(code))) {
      const before = code.slice(Math.max(0, m.index - 40), m.index);
      if (/\bfunction\s+$/.test(before)) continue;
      const close = matching(code, m.index + m[0].length - 1);
      const after = close > 0 ? code.slice(close + 1, close + 160) : '';
      const isDefinition = /^\s*(?::\s*[^{;=]+?)?\s*\{/.test(after) && /(^|[\n;{}]\s*)(?:(?:export|private|public|protected|static|async)\s+)*$/.test(before);
      if (!isDefinition) out.push({ at: m.index, what: name });
    }
  }
  return out;
}

/**
 * Every unguarded destructive command in *files* (`{ name, source }`). `allow` maps
 * `file::enclosing function::command` to a reason. Returns the violations and the
 * allowlist keys that were not needed.
 */
export function scan(files, allow = {}) {
  const used = new Set();
  const violations = [];
  for (const { name: file, source } of files) {
    if (SKIP.includes(file)) continue;
    const code = blank(source);
    const fns = functionsOf(code);
    const guards = guardRanges(code);
    for (const { at, what } of findings(source, code)) {
      if (guards.some(([from, to]) => at > from && at < to)) continue;
      const enclosing = fns.filter((f) => at > f.start && at < f.end).sort((a, b) => b.start - a.start);
      if (enclosing.some((f) => isDestructiveFunction(f.name))) continue;
      const where = enclosing.length ? enclosing[0].name : '(top level)';
      const key = `${file}::${where}::${what}`;
      if (key in allow) {
        used.add(key);
        continue;
      }
      violations.push({ key, file, line: source.slice(0, at).split('\n').length, what, where });
    }
  }
  const stale = Object.keys(allow).filter((k) => !used.has(k));
  return { violations, stale };
}
