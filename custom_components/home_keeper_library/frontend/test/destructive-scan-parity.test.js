import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { scan } from './destructive-scan-lib.js';

// Every command that deletes, removes, disconnects or replaces data must start inside a
// confirmation. A new delete button that runs at once fails this test.
//
// It reads `src/*.ts` as text, so it is a `*-parity` test and the mutation run skips
// it (see `vitest.stryker.config.js`). `destructive-scan-lib.test.js` tests the scanner
// itself on small snippets.

// A command that may run without a question. The key is
// `file::function that holds it::command`. Each entry says why, and an entry that
// nothing needs any more fails the test, so this list cannot collect dead names.
const ALLOW = {
  'tab.ts::_dryRun::importCsv':
    'The preview. It sends dry_run, so it writes nothing. The real import starts in ' +
    '_runImport, and its only caller is inside the Import confirmation.',
};

const SRC = resolve(__dirname, '../src');
const files = readdirSync(SRC)
  .filter((f) => f.endsWith('.ts'))
  .map((name) => ({ name, source: readFileSync(resolve(SRC, name), 'utf8') }));

describe('destructive actions are confirmed', () => {
  const { violations, stale } = scan(files, ALLOW);

  it('has no command that runs a delete without a confirmation', () => {
    const lines = violations.map((v) => `${v.file}:${v.line} ${v.where} runs ${v.what}`);
    expect(lines, 'wrap it in this._confirm(...), or add a reasoned ALLOW entry').toEqual([]);
  });

  it('has no allowlist entry that nothing needs', () => {
    expect(stale).toEqual([]);
  });

  it('gives every allowlist entry a real reason', () => {
    for (const [key, reason] of Object.entries(ALLOW)) {
      expect(reason.length, key).toBeGreaterThan(40);
    }
  });

  it('keeps every websocket command name inside api.ts', () => {
    // A direct `type: 'home_keeper_library/delete_...'` would bypass the names that the
    // scan follows. The tab and the card call `LibraryApi` for each data action.
    const direct = files
      .filter((f) => f.name !== 'api.ts')
      .filter((f) => /['"`]home_keeper_library\/(delete_|remove_|disconnect_|import_|clear_|reset_|purge_|restore_)/.test(f.source))
      .map((f) => f.name);
    expect(direct).toEqual([]);
  });

  it('finds the guarded commands that it should', () => {
    // A scan that sees no command at all would pass for the wrong reason.
    const tab = files.find((f) => f.name === 'tab.ts');
    expect(tab, 'tab.ts must be in src/').toBeDefined();
    for (const command of ['delete_book', 'delete_copy', 'delete_loan', 'delete_room', 'delete_bookcase', 'delete_shelf', 'remove_from_wishlist', 'disconnect_catalog']) {
      expect(tab.source, command).toContain(`'${command}'`);
    }
    expect(tab.source).toContain('_confirm(');
  });

  it('checks the card as well', () => {
    expect(files.map((f) => f.name)).toContain('card.ts');
  });
});
