import { describe, expect, it } from 'vitest';
import { blank, functionsOf, guardRanges, matching, scan } from './destructive-scan-lib.js';

// The scanner on small snippets. It must flag the slip and pass the guarded call.

const run = (source, allow = {}, name = 'tab.ts') => scan([{ name, source }], allow);

describe('scan', () => {
  it('flags a delete that runs at once', () => {
    const { violations } = run("class T { private _act(): void { void this._run('delete_book', { id }); } }");
    expect(violations.map((v) => [v.where, v.what, v.line])).toEqual([['_act', 'delete_book', 1]]);
  });

  it('flags a remove, a disconnect, an import and a restore', () => {
    for (const command of ['remove_from_wishlist', 'disconnect_catalog', 'import_csv', 'restore_backup', 'clear_all', 'reset_state']) {
      expect(run(`function f() { run('${command}'); }`).violations, command).toHaveLength(1);
    }
  });

  it('passes a command inside _confirm or mountConfirm', () => {
    expect(run("function f() { this._confirm(spec, () => this._run('delete_book', {})); }").violations).toEqual([]);
    expect(run("function f() { mountConfirm(p, c, { onConfirm: () => api.call('delete_loan') }); }").violations).toEqual([]);
  });

  it('flags a command after the guard call closes', () => {
    const src = "function f() { this._confirm(spec, () => 1); this._run('delete_book'); }";
    expect(run(src).violations).toHaveLength(1);
  });

  it('passes a command inside a destructive function and checks the callers of that function', () => {
    const body = "async _removeMiss() { await api.call('delete_book', {}); }";
    expect(run(`class T { ${body} }`).violations).toEqual([]);
    expect(run(`class T { ${body} _go() { this._removeMiss(); } }`).violations.map((v) => v.what)).toEqual(['_removeMiss']);
    expect(run(`class T { ${body} _go() { this._confirm(c, () => this._removeMiss()); } }`).violations).toEqual([]);
  });

  it('flags a call of importCsv and ignores its definition', () => {
    expect(run('class A { async importCsv(f: F): Promise<S> { return x; } }').violations).toEqual([]);
    expect(run('function f() { return this._api.importCsv(fields); }').violations.map((v) => v.what)).toEqual(['importCsv']);
  });

  it('ignores a command in a comment, and a name that does not delete', () => {
    expect(run("// this._run('delete_book')\n/* run('remove_x') */ function f() { run('set_reading'); run('return_loan'); run('add_book'); }").violations).toEqual([]);
  });

  it('skips api.ts, which defines the commands', () => {
    expect(run("function f() { call('delete_book'); }", {}, 'api.ts').violations).toEqual([]);
  });

  it('accepts an allowlist entry and reports one that nothing needs', () => {
    const src = "function _dryRun() { return this._api.importCsv(f); }";
    expect(run(src, { 'tab.ts::_dryRun::importCsv': 'x' })).toEqual({ violations: [], stale: [] });
    expect(run('function g() {}', { 'tab.ts::_dryRun::importCsv': 'x' }).stale).toEqual(['tab.ts::_dryRun::importCsv']);
  });
});

describe('helpers', () => {
  it('blanks strings and comments and keeps offsets', () => {
    const src = "a('x_y'); // c\nb";
    const out = blank(src);
    expect(out).toHaveLength(src.length);
    expect(out).toBe("a('   '); // c\nb".replace('// c', '    ').replace(/ {4}\n/, '    \n'));
  });

  it('matches brackets', () => {
    expect(matching('f(a(b)c)', 1)).toBe(7);
    expect(matching('f(a', 1)).toBe(-1);
  });

  it('finds methods and guards', () => {
    const code = blank('class T { async _a(): Promise<void> { this._confirm(c, () => 1); } }');
    expect(functionsOf(code).map((f) => f.name)).toContain('_a');
    expect(guardRanges(code)).toHaveLength(1);
  });
});
