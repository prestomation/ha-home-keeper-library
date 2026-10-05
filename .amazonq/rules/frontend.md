---
title: Frontend rules
summary: Rules for the Library tab and the card - routing through the host, markup, bundles, covers, i18n, layout and Home Assistant elements.
---

# Frontend rules

How the tab and the card work is in [frontend-tab-card](../../docs/design/frontend-tab-card.md).

## Routing

- **The URL is the source of truth.** Every page of the tab maps to a path under
  `/home-keeper/library`: `/books`, `/books/<id>`, `/shelves`, `/loans`, `/wishlist`,
  `/scan`, `/import` and `/settings`. The `route` setter is the only place that changes
  the view state.
- **Navigate only with `host.navigate(path, {replace})`.** The Home Keeper panel owns
  the browser history, so the tab never calls `history.pushState`. Opening a detail
  pushes. Closing a detail or deleting a book replaces, so Back moves inside the tab.
- Keep `parseRoute` and `buildPath` pure in `utils.ts`, so they unit-test and round-trip.
  An unknown path falls back to the book list. A detail URL for a deleted book shows the
  gone notice.
- **The filters of a view are `;key=value` parameters on the last path segment**, as in
  `/books;q=le%20guin;status=read`. The Home Keeper host gives the tab only the path and
  drops a `?query`. A default value is left out of the URL. `parseRoute` still reads a
  `?query`, so an old link works.
- **A new URL segment keeps old URLs working.** A user can bookmark any tab URL.
- Dialogs are not deep-linked. A dialog is a short-lived form on its page.

## Markup and text

- Escape all user content with `escapeHTML` before it goes into `innerHTML`.
- Notes render through the `ha-markdown` element of Home Assistant, which cleans the
  HTML. The bundle has no Markdown parser. Until the element loads, the text shows as
  escaped plain text.
- All UI text comes from `t()` and `tn()` in `i18n.ts`. A lookup falls back to English and
  then to the raw key, so a missing translation never renders `undefined`.
- Every control has a stable `data-k` attribute, so a render keeps the focus, the caret
  and the typed text (`dom.ts`).

## Bundles and the card

- 2 ES module bundles ship from `frontend/dist/` at `/home_keeper_library_static`: the tab
  (`library-tab.js`, loaded by the Home Keeper panel) and the card (`library-card.js`).
  Each URL carries a content hash in `?v=`.
- **Deliver the card by 1 path only**: a Lovelace resource, or `frontend.add_extra_js_url`
  when the resources are in YAML or the resource write fails (`card.py`). Both paths
  together are a race in the scoped element registry of Home Assistant 2026.9.
- The barcode decoder is a separate chunk. It loads only when the scanner opens on a
  browser with no native `BarcodeDetector`. Import nothing from `@zxing/library` outside
  `zxing-decoder.ts`.
- The card works for every user. It never shows a management control.
- On a cold frontend the card element can upgrade after the dashboard renders. The e2e
  helper `openCard` retries with a reload. Do not remove the retry.
- **Never tear down the tab registration or the card resource on unload.** Only the Home
  Keeper link removes the tab, when Home Keeper goes away. Only `async_remove_entry`
  removes the card resource.
- A cover is served by an authenticated view. An `<img>` element cannot send a token, so
  sign the path with `auth/sign_path` or read the image with `fetchWithAuth`.

## Layout

- **Only CSS picks the layout.** Breakpoints are viewport `@media` queries. The phone
  layout starts below 700 px. Nothing in a render function reads the viewport.
- Review each changed surface at desktop and phone width
  ([pr-workflow.md](pr-workflow.md#screenshots-desktop-and-phone)).
- State shown by color has a text equivalent.
- Do not declare a widget role that you have not implemented.

## Camera

- The camera needs a secure origin. If `navigator.mediaDevices` is missing, show the
  HTTPS message and offer **Enter ISBN**.
- An EAN-13 with the `978` or `979` prefix is an ISBN. The scanner ignores the same code
  for 3 seconds.

## Home Assistant elements

- **Use only HA elements that the Home Keeper panel page registers.** Check with
  `customElements.get('<tag>')` in the e2e container. Otherwise build from plain DOM and
  theme variables.
- **Probe a real element before you design against it.** `observedAttributes` tells you
  what it still reads. Assert on rendered pixels, not markup, where HA draws.
- Every style rule reads a `--hkl-*` token, and each token resolves to a Home Assistant
  theme variable with a literal color only as the fallback. Cover and spine colors are
  artwork and stay literal.
