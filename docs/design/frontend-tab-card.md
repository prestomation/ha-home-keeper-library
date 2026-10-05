---
title: Tab and card
summary: How the Library tab runs inside the Home Keeper panel, how the card shows the reading of a person, and how both read the state, route, render, translate and ship.
implements:
  - custom_components/home_keeper_library/frontend_assets.py
  - custom_components/home_keeper_library/frontend/src/tab.ts
  - custom_components/home_keeper_library/frontend/src/tab-index.ts
  - custom_components/home_keeper_library/frontend/src/tab-types.ts
  - custom_components/home_keeper_library/frontend/src/tab-books.ts
  - custom_components/home_keeper_library/frontend/src/tab-shelves.ts
  - custom_components/home_keeper_library/frontend/src/tab-lists.ts
  - custom_components/home_keeper_library/frontend/src/tab-dialogs.ts
  - custom_components/home_keeper_library/frontend/src/card.ts
  - custom_components/home_keeper_library/frontend/src/card-index.ts
  - custom_components/home_keeper_library/frontend/src/api.ts
  - custom_components/home_keeper_library/frontend/src/types.ts
  - custom_components/home_keeper_library/frontend/src/utils.ts
  - custom_components/home_keeper_library/frontend/src/i18n.ts
  - custom_components/home_keeper_library/frontend/src/locales/index.ts
  - custom_components/home_keeper_library/frontend/src/markup.ts
  - custom_components/home_keeper_library/frontend/src/markdown.ts
  - custom_components/home_keeper_library/frontend/src/dom.ts
  - custom_components/home_keeper_library/frontend/src/styles.ts
  - custom_components/home_keeper_library/frontend/src/global.d.ts
related: [home-keeper-dependency, scan-and-isbn, csv-import-export, people-privilege]
source_hash: 17b75214ddf4
---

# Tab and card

The frontend is 2 ES modules: the Library tab, which the Home Keeper panel loads for
admins, and the card, which any user adds to a dashboard. Both are plain custom elements
with no runtime framework. The rules for a change are in
[frontend.md](../../.amazonq/rules/frontend.md).

## Goals

- **G1. The URL is the state.** Every page of the tab has a URL, and Back and Forward
  move inside the tab.
- **G2. Same data, same rules.** The tab and the card read 1 projected state from
  `get_state`, so the card of a non-admin user shows only what that user can read.
- **G3. Works on a phone.** Each view works at phone width, and the scan flow is built
  for it.
- **G4. Translated.** Every label comes from the locale tables of the 16 languages.

## Non-goals

- Management in the card. The card sets the reading status of its person and no more.
- A router or a component framework.
- Offline edits. Each change is a websocket call.

## Design

### Delivery

`frontend_assets.async_register` serves `frontend/dist/` at
`/home_keeper_library_static`, and adds `library-card.js?v=<hash>` as an extra module,
so the card is in the card picker with no resource to add. The tab URL with its hash goes
to Home Keeper ([home-keeper-dependency](home-keeper-dependency.md)). Rollup builds
`tab-index.ts` and `card-index.ts`, with the locale tables and `PANEL_VERSION` inlined,
and the zxing decoder as a separate chunk.

### State

`api.ts` wraps the websocket commands. The tab and the card call `get_state`, then
`subscribe`, and read `get_state` again after each `changed` message.
`utils.normalizeState` turns the reply into arrays in display order, and
`utils.buildIndex` makes the lookups of a render. A cover upload posts the file with
`fetchWithAuth` and calls `set_cover` with the returned `file_id`.

### The tab

The Home Keeper panel sets `hass`, `narrow`, `route` and `host` on
`home-keeper-library-tab`. `route.path` is the path after `/home-keeper/library`.
`utils.parseRoute` turns it into a view, an id and a query, and `utils.buildPath` is the
inverse. The tab moves only with `host.navigate`, and shows notices with
`host.showToast`. `host.taskLink` links a loan to its Home Keeper task.

| Path | View | Module |
|---|---|---|
| `/books`, `/books/<id>` | Book list with filters, book detail | `tab-books.ts` |
| `/shelves`, `/shelves/<room_id>` | Rooms and shelves | `tab-shelves.ts` |
| `/loans?tab=out\|in\|returned` | Loans | `tab-lists.ts` |
| `/wishlist`, `/settings` | Wishlist, people settings | `tab-lists.ts` |
| `/scan`, `/import` | Scan flow, import | `tab-scan.ts`, `tab-import.ts` |

The book filters are in the query: `q`, `status`, `room`, `shelf`, `reader`, `subject`,
`owned`, `sort` and `view`. `utils.filterBooks` and `utils.sortBooks` apply them.
Each view is a free function over `ViewCtx` (`tab-types.ts`) that returns 1 HTML string.
`tab.ts` renders it with `dom.renderKeepFocus`, and 1 delegated listener for each event
type reads the `data-act`, `data-chg`, `data-input` and `data-form` attributes. The
dialogs of `tab-dialogs.ts` are a separate layer, so a data push does not clear a form.

### The card

`home-keeper-library-card` shows the person of the user, or the `person` of the config for
an admin. Its sections are search with the location of each result, Reading with the
page and a Read button, Want to read with a random pick, the yearly goal and the household
activity of the people who share their reading. Each section has a toggle in the visual
editor. The card calls `set_reading` with no `person_id` for its own person.

### Markup, text and style

- `markup.ts` builds the shared pieces, such as a cover, a status label and a person dot,
  and escapes each user value with `utils.escapeHTML`. A cover with no file is a colored
  block with the initials. A stored cover is an `<img>` of `cover_url`. The cover view
  requires a token, and the path is not signed yet ([IDEAS.md](../../IDEAS.md#known-gaps)).
- `markdown.ts` renders the notes with `ha-markdown`, and plain escaped text until the
  element loads.
- `i18n.ts` picks the table of the Home Assistant language, then its base language, then
  English, with `t()`, `tn()` and the number, date and money formats.
- `styles.ts` defines the `--hkl-*` tokens from the Home Assistant theme variables. The
  phone layout starts below 700 px, in CSS only.

## Trade-offs

- **1 HTML string for each render** over **a virtual DOM**: no dependency, and the views
  test as pure functions in jsdom. The cost is the focus helper.
- **Read the whole state** over **query each view**: every view and filter works on local
  data. The design size of 5000 books is 1 reply of a few MB.

## One-way doors

- The element names `home-keeper-library-tab` and `home-keeper-library-card`, and the
  bundle names `library-tab.js` and `library-card.js`.
- The tab paths and query keys, because a user can bookmark them.
- The card config keys `person`, `title`, `search`, `reading`, `want`, `goal` and
  `household`.
