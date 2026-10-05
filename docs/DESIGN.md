# Design notes

This template demonstrates a complete Home Assistant custom integration in
miniature. The feature — an **items list** (named items, each with a numeric
`value`) — is intentionally trivial so the *structure* is the lesson.

## Layers

```
                  ┌───────────────────────────────────────────────┐
  Pure core       │ models.py   events.py        (no HA imports)   │
  (unit-tested)   └───────────────────────────────────────────────┘
                            ▲                ▲
                            │ build/validate │ build payloads
                  ┌─────────┴────────────────┴────────────────────┐
  HA boundary     │ store.py  ── the single mutation chokepoint    │
                  │   • validates via models                       │
                  │   • persists to .storage/home_keeper_library   │
                  │   • fires bus events (events.py)               │
                  └───────────────┬───────────────────────────────┘
                                  │ read via
                  ┌───────────────┴───────────────────────────────┐
  Surfaces        │ coordinator → sensor entities (usage/display)  │
                  │ services (__init__.py) — automation contract   │
                  │ websocket_api — panel/card UI optimization     │
                  │ panel.py + card.py — register the frontend     │
                  └───────────────────────────────────────────────┘
```

## Key decisions

- **Pure, HA-free core.** `models.py`/`events.py` are pure so the highest-value
  logic unit-tests without the HA harness (tier 1).
- **One mutation chokepoint.** Every write goes through `HomeKeeperLibraryStore`; events fire
  there, so all surfaces are observed uniformly.
- **Services are the contract; the websocket is an optimization.** The panel/card
  use websocket commands for latency, but they delegate to the same store methods
  the services call. Automations get a real `home_keeper_library.*` service.
- **Immediate refresh.** Mutations call `coordinator.async_refresh()` (not the
  debounced `async_request_refresh()`) so the local store stays instantly
  consistent and tests are deterministic.
- **Admin vs. usage split.** Management lives in the sidebar panel; display lives in
  native sensor entities and the dashboard card.
- **Deep-linked panel.** The URL is the single source of truth (`parseRoute`/
  `buildPath` are pure); Back/Forward move within the panel.

## People and privacy

Home Assistant shows each entity to each user, and lets each user call the
`todo` services on each to-do list. So the per-person entities apply the
privacy rules of the library themselves:

- **The `To read` list of a person** takes a change (add, update or delete an
  item) only from the user of that person, from an admin user, or from Home
  Assistant itself (no user). The entity service call sets the context of the
  call on the entity, and the list reads `user_id` from it. Other users get the
  translated error `todo_not_allowed`.
- **A person with `share_reading: false`** shows no reading on an entity. The
  `To read` list and the `Books read this year` and `Reading now` sensors of
  that person are unavailable, and the list gives no items, also through
  `todo/item/list`. They come back when sharing is on again.

## Why four test tiers
See `.amazonq/rules/testing-and-workflow.md`. In short: pure unit (ms), in-process
HA component (≈100ms, real `hass`), Docker integration (real running HA over REST/WS),
and Playwright e2e (browser). The component tier is the workhorse for HA-coupled
logic; Docker is reserved for what the in-process harness can't do (serving bundles,
registering panel/card resources, full-stack REST).
