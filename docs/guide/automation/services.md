# Services and events

Each operation of the Library tab is a `home_keeper_library.*` service. Automations,
scripts and voice assistants can use the services to change the library, and the bus
events to react to a change.

## Services

The services are in **Developer tools → Actions**, with a description of each field.
Most services are admin-only. `set_reading`, `set_person_settings` and the read services
are open to every user, for their own person
([People and privacy](../start/people-and-privacy.md)).

Example: set the status Read when an NFC tag on the bookcase is scanned.

```yaml
automation:
  - alias: Finished a book
    triggers:
      - trigger: tag
        tag_id: bedside-book
    actions:
      - action: home_keeper_library.set_reading
        data:
          book_id: "5f0c1b2a9d8e4f7a8b6c5d4e3f2a1b0c"
          person_id: "alice"
          status: read
```

A read service returns a response. Example: find the shelf of a book.

```yaml
actions:
  - action: home_keeper_library.list_books
    data:
      query: dune
    response_variable: found
  - action: home_keeper_library.get_book
    data:
      book_id: "{{ found.books[0].id }}"
    response_variable: detail
```

## Events

The library fires an event for each change, such as
`home_keeper_library_book_finished`, `home_keeper_library_loan_started` and
`home_keeper_library_loan_overdue`. Use them with an **Event** trigger.

```yaml
automation:
  - alias: Overdue loan reminder
    triggers:
      - trigger: event
        event_type: home_keeper_library_loan_overdue
    actions:
      - action: notify.notify
        data:
          message: "{{ trigger.event.data.title }} was due on {{ trigger.event.data.due }}."
```

## Entities

| Entity | State |
|---|---|
| **Books** | The books with 1 copy or more |
| **Loans out** | The open loans of lent copies |
| **Loans overdue** | The open loans past their due date |
| *Person* **books read this year** | The books read this year, with the goal and the pages |
| *Person* **reading now** | The books with status Reading, with their titles |
| *Person* **to read** | A to-do list of the books with status Want to read |

Complete an item of a **to read** list to set the status Read. Add an item to add a book
to the list. The per-person entities follow the privacy rules in
[People and privacy](../start/people-and-privacy.md#entities).

## Reference

- [Integrating](https://prestomation.github.io/ha-home-keeper-library/developer/integrating)
  has the services by group and the contract for other integrations.
- [Events](https://prestomation.github.io/ha-home-keeper-library/developer/events) has
  each event, its payload and when it fires.
- [API reference](https://prestomation.github.io/ha-home-keeper-library/developer/api)
  has every service field, event payload and entity attribute.
