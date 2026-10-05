---
title: People and privilege
summary: How the library finds the person of a caller, which operations are admin-only, which act for the caller's own person, and what each projection hides.
implements:
  - custom_components/home_keeper_library/people.py
  - custom_components/home_keeper_library/projections.py
related: [events-api, entities, architecture]
source_hash: 6a8778e85772
---

# People and privilege

A person in the library is a Home Assistant `person`. Admins manage the catalog. Every
user keeps the reading status, the rating and the notes of their own person. Each read
goes through a projection, so a reply holds only what the caller can read. The security
summary for users and integrators is [SECURITY.md](../SECURITY.md).

## Goals

- **G1. A reply never leaks.** A non-admin user reads no price, value or source of a copy,
  no party of a loan, and no private notes of another person.
- **G2. Opt-in sharing.** The reading status of a person shows to other non-admin users
  only while that person shares it.
- **G3. One gate.** The service and its websocket twin pass the same check, so a gate
  cannot be on 1 path only.
- **G4. Rename-safe people.** A person is the collection id, so a new name or a new user
  keeps the reading history.

## Non-goals

- Privacy between admins. An admin reads the full document.
- Per-book access rules. A book, its shared notes and its cover are open to every user.
- Library accounts of their own. The library uses the Home Assistant users and persons.

## Design

### The caller

`people.actor_for_user` turns a Home Assistant user into an `Actor`: the user id, the
admin flag and the person whose `user_id` is that user. A websocket command takes the
admin flag from the connection user. A call with no user id comes from an automation or
the core: it is trusted, with `is_admin` true and no person.

`people.persons` lists each `person.*` state with its collection id (the `id` attribute),
its name, its entity id and its user id, sorted by name.

### Gates

`services.async_run` runs every operation. It refuses a non-admin caller of an
`admin_only` spec with `Unauthorized`. The 2 `caller_scoped` services are open:

- `set_reading` acts for the caller's person. A non-admin user who names another person
  gets `Unauthorized`. A caller with no person gets `no_person`.
- `set_person_settings` lets a non-admin user change `share_reading` and `yearly_goal`
  of their own person. `wishlist_todo` is admin-only, because it sends text to a to-do
  list.

The read services `list_books`, `get_book`, `list_locations`, `list_loans` and
`list_people` are open and projected. `get_state` and `subscribe` are open.
`list_todo_entities` and the cover upload are admin-only. The cover view is open to
each signed-in user, because covers are not private.

### Projections

`projections.project_state` builds the reply of `get_state`, and
`projections.project_book` builds each book in a service reply. For a non-admin viewer:

- a copy drops `PRIVATE_COPY_FIELDS` (`price`, `value`, `acquired_from`);
- a loan drops `PRIVATE_LOAN_FIELDS` (`party`);
- the reading row of another person shows only with `share_reading: true`, and drops
  `private_notes`;
- the settings of another person drop `wishlist_todo`.

The viewer's own rows are full. Each book also gets `owned`, `copy_count` and
`cover_url`. The sensors and the card use the count functions at the end of the module.

### Entities

An entity has no projection: Home Assistant gives its state to each user. So the
per-person entities of [entities](entities.md) check the privacy rules in the entity:

- `PersonEntity.available` is false while the settings of the person have
  `share_reading: false`. The To read list then gives an empty `todo_items`.
- `ToReadList` checks the caller before each item add, update and delete. The entity
  service call of Home Assistant sets the context of the call on the entity, and the list
  reads its `user_id` through `people.actor_for_user`. The user of the person, an admin
  and a call with no user pass. Another user gets `todo_not_allowed`.

## Trade-offs

- **Project the reply** over **gate the read**: the card and the entities work for every
  user, and the private fields stay with the admins.
- **Sharing on by default** (`share_reading: true`) over **off by default**: the
  household section of the card shows the shared reading. A person can turn it off with
  `set_person_settings`.
- **Trust a call with no user** over **refuse it**: Home Assistant core trusts it too, and
  automations need it.

## One-way doors

- The admin flag of each service in `api_surface.SERVICES`. Opening an admin-only
  service later is a change to the security model.
- The private field lists. A field that a non-admin can read now is hard to hide later.
- `share_reading` and its default, and its effect on the per-person entities.
