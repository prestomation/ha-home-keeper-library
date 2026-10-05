---
title: Loans and Home Keeper tasks
summary: How the library records lent and borrowed books, and keeps 1 one-off Home Keeper task for each loan with a due date.
implements:
  - custom_components/home_keeper_library/loan_tasks.py
  - custom_components/home_keeper_library/loan_sync.py
related: [store-models, home-keeper-dependency, events-api]
source_hash: 0884d41fbfac
---

# Loans and Home Keeper tasks

A loan is a copy that the household lent out (`direction: out`), or a book that a person
borrowed (`direction: in`). A loan with a due date can have a one-off task in Home
Keeper, so the return shows in the to-do list, the calendar and the notifications of Home
Keeper. The contract is sections 1 to 6 of the Home Keeper `docs/INTEGRATING.md`.

## Goals

- **G1. 1 task for each loan.** A loan with `add_task: true` and a due date has at most 1
  Home Keeper task, bound by the loan id in the task source.
- **G2. Both ways.** A return in the library completes the task. A completed task in Home
  Keeper returns the loan.
- **G3. No loops.** Each call to Home Keeper sends the library origin, and the listeners
  ignore an event with that origin.
- **G4. The user decides.** A task that a user deletes in Home Keeper is not added again.

## Non-goals

- Reminders of the library's own. Home Keeper owns the notifications of a task.
- Tasks for a loan with no due date.
- Loans of a book that the library does not hold. A borrowed book is a book with no copy.

## Design

### Loan records

- `lend_book` takes a `copy_id` and a `party`. The copy keeps its shelf and can have only 1
  open loan.
- `borrow_book` takes a `book_id`, an ISBN or a title, a `party` and a `person_id`. It
  adds the book when none matches, and adds no copy. The status of the person becomes
  `reading` if it is `want` or absent.
- `return_loan` sets `returned`, today by default. A returned loan stays in the history.
- `update_loan` changes the party, the dates, the format or the note. `delete_loan`
  removes the loan from the history.
- `LibraryStore.fire_overdue` runs at setup and each hour, and fires `loan_overdue` once
  for each due date.

### Planner

`loan_tasks.plan_reconcile` takes the loans and the task list of the Home Keeper service
`list_tasks`,
and returns a `LoanTaskPlan`:

- an open loan that wants a task and has none gets an `adds` step, unless a task with its
  loan id exists: then a `binds` step records that task;
- a returned loan with an open task gets a `completes` step;
- a task whose loan is deleted, or wants no task, gets a `deletes` step;
- a task with an old due date gets a `due_updates` step;
- a bound task that is gone gets a `forgets` step, and the loan gets a new task on the
  next pass;
- a completed task of an open loan gets a `returns` step.

`loan_tasks.add_task_payload` builds the fields of the Home Keeper service `add_task`:
the name, the type `one-off`, the due date, `source: {"home_keeper_library": {"loan_id": id}}`, and
`managed_by` with the library name, the icon, the config entry id, the locked fields
`name` and `recurrence_type`, and the completion prompt. The name comes from
`backend_strings` in the Home Assistant language: "Get {title} back from {party}" for a
lent copy, "Return {title} to {party}" for a borrowed book.

### Sync

`LoanSync` runs a pass at start, when Home Keeper becomes available, and after each store
change that changes a loan. A lock runs 1 pass at a time. A pass that changed the loans
runs once more. Each call is guarded with `has_service` and is best effort: a failed call
is tried again on the next pass. The sync runs only while `HomeKeeperLink` says that Home
Keeper takes loan tasks.

- `home_keeper_task_completed` with the source of an open loan returns the loan with the
  library origin.
- `home_keeper_task_deleted` with the task id of a loan clears the task id and turns
  `add_task` off.

## Trade-offs

- **A reconcile pass** over **1 call for each change**: a pass also repairs a task that
  was lost while Home Keeper was not loaded. The cost is a `list_tasks` call for each loan
  change.
- **Delete the task of a deleted loan with `force`** over **leave it**: a task with no
  loan has no meaning in Home Keeper.
- **Lock the task name** over **let the user rename it**: the library writes the name from
  the title and the party.

## One-way doors

- The task source key `home_keeper_library` and its field `loan_id`. Home Keeper stores it
  in each task.
- The loan fields `direction`, `party`, `started`, `due`, `returned`, `add_task` and
  `hk_task_id`.
- The `managed_by` block that Home Keeper shows for a library task.
