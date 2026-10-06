---
title: Home Keeper dependency
summary: How the library checks Home Keeper, registers its tab and its companion entry, and shows a repair issue in place of a setup failure.
implements:
  - custom_components/home_keeper_library/home_keeper.py
related: [architecture, loans-home-keeper, frontend-tab-card]
source_hash: 4b6ddf69e66f
---

# Home Keeper dependency

The library requires Home Keeper for 2 things: the Library tab in the Home Keeper panel,
and the loan tasks. Everything else works without it. Home Keeper is an
`after_dependencies` entry in the manifest, so the library loads after Home Keeper when
both are present, and loads alone when Home Keeper is absent.

## Goals

- **G1. Say why.** If Home Keeper is missing, not set up or too old, the config flow
  stops with that reason, and a running library shows a repair issue with the same
  reason.
- **G2. Never block setup.** The library never raises `ConfigEntryNotReady` for Home
  Keeper, because a retry cannot install or update it.
- **G3. Follow Home Keeper.** When Home Keeper loads, unloads or updates, the tab and the
  loan tasks follow with no restart.

## Non-goals

- A copy of Home Keeper features, such as a panel of the library's own.
- A version check of the library against Home Keeper beyond the panel tab API.

## Design

### The check

`home_keeper.async_check` returns a reason or None:

| Reason | When |
|---|---|
| `home_keeper_missing` | Home Assistant has no `home_keeper` integration. |
| `home_keeper_not_set_up` | Home Keeper has no loaded config entry. |
| `home_keeper_too_old` | There is no `panel_tabs` module. The version number is not checked, so a Home Keeper beta works. |

Each reason is a config flow abort reason and a repair issue with the same translation
key. The placeholders give the install URL and the minimum version.

### The link

`HomeKeeperLink` runs the check at setup, on each config entry change of Home Keeper, and
when the `home_keeper` component loads. A lock runs 1 check at a time. Each check:

1. Shows the repair issue of the reason, and deletes the other 2. A pass deletes all 3.
2. Turns the loan sync on only while the check passes.
3. On a failure, removes the tab.
4. On a pass, registers the tab if it has none. If Home Keeper was not available before,
   it registers the companion and schedules a loan sync pass.

The repair issue is not fixable from the repairs dialog and is not persistent, so it goes
away when the check passes.

### The tab

`_register_tab` imports `custom_components.home_keeper.panel_tabs` in an executor job and
calls its `async_register_panel_tab` with a `PanelTab`:

- `companion` `home_keeper_library`, `id` `library`, `icon` `mdi:bookshelf`, `order` 50;
- `titles`: the `tab.title` of each language in `backend_strings`;
- `module_url`: `/home_keeper_library_static/library-tab.js?v=<content hash>`;
- `element` `home-keeper-library-tab` and `host_api` 1.

The returned callable removes the tab. If Home Keeper refuses the tab, the library logs
the reason and runs without it. The coordinator flag `tab_registered` goes to the
diagnostics, and to `get_state` as `tab` in the `home_keeper` block.

### The companion

`home_keeper.async_register_companion` calls the Home Keeper service
`register_companion` with the
domain, the name, the icon, the description from `backend_strings`, the config entry id
and the docs URL. It runs when Home Keeper becomes available, and again on each
`home_keeper_register_companions` event. A failure is logged at debug level.

## Trade-offs

- **`after_dependencies`** over **`dependencies`**: with a hard dependency, Home Assistant
  refuses the config flow and shows no reason. The cost is the run-time check.
- **A repair issue and a running library** over **a failed setup**: the card, the
  entities and the services keep working, and the user sees 1 clear action.
- **An import of the Python module** over **a service call for the tab**: the tab needs a
  callable to remove it on unload.

## One-way doors

- The tab id `library`, the element name `home-keeper-library-tab`, the host API version
  1 and the tab path `/home-keeper/library`.
- The repair issue ids, which match the abort reasons.
- `const.HOME_KEEPER_MIN_VERSION`, which users read in the repair issue.
