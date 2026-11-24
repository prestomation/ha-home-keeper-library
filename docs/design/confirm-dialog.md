---
title: Confirm before data loss
summary: How the Library tab asks before it deletes, removes, disconnects or imports, with 1 dialog and 1 scan test.
implements:
  - custom_components/home_keeper_library/frontend/src/confirm-dialog.ts
  - custom_components/home_keeper_library/frontend/src/confirm-specs.ts
related: [frontend-tab-card, home-keeper-dependency]
source_hash: 136c5a5509ea
---

# Confirm before data loss

The tab asks before each action that loses data or is hard to reverse. The rules and the
wording are the same as in the Home Keeper panel. The rules for a change are in
[frontend.md](../../.amazonq/rules/frontend.md#confirm-before-data-loss).

## Goals

- **G1. 1 door.** Each delete, remove, disconnect and import runs from the confirm button of
  1 dialog. A test fails the build for a command that runs outside it.
- **G2. Safe by default.** Cancel has the keyboard. Escape and a tap outside cancel.
- **G3. The dialog says what happens.** It names the item, gives the real counts of what goes
  with it, and the button names the action.
- **G4. Same as Home Keeper.** The behavior and the wording rules match the Home Keeper panel.

## Non-goals

- Undo. A confirmed action stays done.
- A confirm for an action that the user can reverse or that is frequent, such as a reading
  status change, a loan return, a move or an edit form.
- A confirm in the card. The card has no destructive action.

## Design

`tab.ts` `_confirm(content, run)` is the only door. It closes any open confirm, mounts
`confirm-dialog.ts` into the shadow root of the tab, and starts `run` only from the confirm
button. The shadow root gives the dialog the `--hkl-*` tokens. The dialog is an `alertdialog`
that is named by its heading and described by its body. Cancel, Escape and a tap on the scrim
close it, Tab stays inside, and the focus returns to the control that opened it. A key press never
reaches the handlers of the tab below it. The dialog is removed when the tab leaves the page.

`confirm-specs.ts` has the pure text of each dialog. It names the item, gives the counts
from the index (copies, loans and reading statuses of a book, the bookcases and shelves of a
room, the copies that lose a shelf), and ends a delete with "You cannot undo this." The button
reuses the name of the action, such as **Delete book**.

A command that deletes, removes, disconnects or replaces data runs inside `_confirm`. This
covers a book, a copy, a loan, a room, a bookcase, a shelf, a wishlist entry, the Open
Library connection, a scan with no match, a custom cover that the Open Library cover replaces,
and the CSV import. A failed command shows a toast and the page stays as it was.

`frontend/test/destructive-scan-parity.test.js` reads `src/*.ts` as text. It finds each command
string that starts with `delete_`, `remove_`, `disconnect_`, `import_`, `clear_`, `reset_`, `purge_`
or `restore_`, and each call of `importCsv`. It requires the command to be inside `_confirm`
or `mountConfirm`. An allowlist entry needs a written reason, and a stale entry fails. A second
test keeps the websocket command names inside `api.ts`.

## Trade-offs

- **A copy of the dialog** over **the dialog of the host**: the host API (version 1) has no
  confirm function. The cost is 2 copies of the same rules. A host function would need a
  new host API version and a minimum Home Keeper version.
- **A text scan** over **a type check**: no tool chain, and it fails on the common slip. It
  cannot see a command that goes through a variable.
- **Counts as plain lines** over **a sentence with plural forms**: 1 key for each count, and no
  plural rules for 16 languages.

## One-way doors

- None. The dialog is frontend code. It adds no service field, event, attribute or storage key.
