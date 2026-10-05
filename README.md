# Home Keeper Library

[![GitHub Release][release-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacs-shield]][hacs]
[![HACS Validation][hacs-validation-shield]][hacs-validation]

**Home Keeper Library requires [Home Keeper](https://github.com/prestomation/ha-home-keeper).
Install and set up Home Keeper first.**

Home Keeper Library is a Home Assistant integration for the books of a household. It
records the rooms, bookcases and shelves of the home, the books and their copies, the
reading status of each person, the loans and a wishlist. Admins manage it in a
**Library** tab of the Home Keeper panel. Every user gets a dashboard card, sensors and a
To read list.

<!-- screenshot: books-desktop.png -->

## Features

- Scan the ISBN barcode of each book with a phone. Details and covers come from
  [Open Library](https://openlibrary.org).
- Find each book on its room, bookcase and shelf.
- Keep a reading status, a rating, notes and a yearly goal for each person.
- Lend and borrow books, with a Home Keeper task on each due date.
- Send the wishlist books to buy to a to-do list of the person.
- Import a Goodreads or StoryGraph CSV file, and export to one.

## Install

1. Install and set up [Home Keeper](https://github.com/prestomation/ha-home-keeper#installation).
2. In [HACS](https://hacs.xyz/), add this repository as a custom repository, with the
   category **Integration**: `https://github.com/prestomation/ha-home-keeper-library`.
3. Install **Home Keeper Library** and restart Home Assistant.
4. Add the integration in **Settings → Devices & services → Add integration → Home
   Keeper Library**.

## Documentation

The [user guide](https://prestomation.github.io/ha-home-keeper-library/docs/intro) has
each feature, with screenshots. The
[developer guide](https://prestomation.github.io/ha-home-keeper-library/developer/integrating)
has the services, the events and the API reference. The sources are in
[`docs/guide/`](docs/guide/) and [`docs/`](docs/).

## Run the tests

The tiers, cheapest first, are in [`.amazonq/rules/testing.md`](.amazonq/rules/testing.md).

```bash
bash ci/setup-ci-deps.sh            # all CI dependencies into .venv
bash ci/test-python-unit.sh         # pure unit, no Home Assistant
bash ci/test-python-component.sh    # in-process Home Assistant, fake Home Keeper
bash ci/test-frontend.sh            # vitest
bash ci/e2e-up.sh                   # Docker and Playwright, with the real Home Keeper
ruff check . && ruff format --check . && mypy custom_components/home_keeper_library
python3 ci/docs.py check
```

> **Warning:** run the component tier and the Docker integration tier in separate pytest
> runs. `pytest-homeassistant-custom-component` pulls in `pytest-socket`, which blocks
> the real network that the Docker tier needs.

## Guardrails

Each check catches a failure that leaves no trace on its own. The workflow and the
conventions behind them are in [`AGENTS.md`](AGENTS.md) and
[`.amazonq/rules/`](.amazonq/rules/).

**On every pull request:**

| Guardrail | Where | What it catches |
|---|---|---|
| **ruff** lint and format | `lint.yml` | Style and format drift in the Python code. |
| **mypy**, strict, with Home Assistant | `lint.yml` | Type errors against the real Home Assistant API, from `requirements-typing.txt`. |
| **Stale Home Assistant resolve** | `ci/check-ha-version.py` | pip that goes back to an old Home Assistant on an old Python, while the job stays green. |
| **Prose linting** | `lint.yml` (vale) | AI-writing tells and breaks of the STE rules (`styles/STE/`) in the docs and the strings that Home Assistant shows. Scoped to the changed lines. |
| **Docs audit** | `lint.yml` (`docs-audit`, `ci/docs.py check`) | A design doc that no longer matches its code, a source file that no design doc covers, a doc over its cap, history in a doc, a broken link, and a reference to a file or function that does not exist. |
| **CHANGELOG release gap** | `ci/check-changelog-release-gap.py` | An entry in a section that is already tagged, `manifest.json` and `PANEL_VERSION` that differ, and a top section that no version bump releases. |
| **The test tiers** | `test.yml`, `integration.yml`, `e2e.yml` | Pure unit, in-process Home Assistant with a fake Home Keeper, Docker with the real Home Keeper, and Playwright at desktop and phone width. |
| **Mutation testing at 80%** | `mutation.yml` | A test that runs a line and asserts nothing that would catch a wrong line. Scoped to the changed code. |
| **Coverage comment** | `pytest_coverage.yml` | New code with no test, shown in the review. |
| **Translation parity** | `tests/unit/test_translations_parity.py`, `frontend/test/i18n-parity.test.js` | A missing key, a different `{placeholder}` and English text in another locale, for 16 languages. |
| **Localized exceptions** | `tests/unit/test_exception_translations.py` | An error that a user can see with no `translation_key`, and a key with no message. |
| **Exact shapes** | `tests/unit/test_shapes.py` | A record or reply key that changed name on both sides of a round trip. |
| **Pure core** | `tests/unit/test_pure_core.py` | A Home Assistant import in a pure module, and a module map that does not match the code. |
| **API-surface drift** | `tests/unit/test_api_surface.py` | A service, event, payload field, websocket command, entity platform or HTTP view added to 1 registry and not to `api_surface.py`. |
| **Generated API reference** | `tests/unit/test_generate_api_docs.py` | A surface in `api_surface.py` that the reference page leaves out. |
| **Seeded fixture** | `tests/unit/test_integration_fixture_clean.py` | A local Docker run committed into the seeded config entries of Home Keeper and the library. |
| **Docs site build** | `docs-preview.yml` | A guide page with no sidebar entry, a broken link or anchor, and a missing image. Posts a preview link. |
| **Walkthrough capture** | `walkthrough-preview.yml` | A tour that no longer runs. A failed capture fails the check. |
| **Pinned actions and read-only tokens** | `tests/unit/test_ci_action_pins.py` | A third-party action that is not pinned in a job that can write. |
| **HACS validation and hassfest** | `test.yml`, `hacs.yml` | Manifest, brand and repository problems that block an install. |
| **Release consistency** | `release.yml` | A `manifest.json` version, `PANEL_VERSION` and CHANGELOG section that disagree. |
| **Release publish gate** | `release.yml`, `tests/unit/test_ci_release_publish_gate.py` | A tag, a release or a docs deploy from a branch other than `main`, or from a dry run. |
| **Dependabot auto-merge** | `dependabot-auto-merge.yml`, `ci/wait_for_checks.py` | A bump that merges before every check on its head commit is green. |

**After a release:** `notify-issues` in `release.yml` comments on each `(Fixes #N)` issue
that the release names, and closes it on a stable release (`ci/release-issues.py`).

**Nightly, gating nothing:** `ha-beta.yml` runs the Docker and browser tiers against the
Home Assistant beta and type-checks against a pre-release, then files 1 reusable issue.

**In review:** desktop and phone screenshots of each changed UI surface, a walkthrough
step for each new UI feature, and the **One-way doors** and **Security** sections of the
PR body (`.github/pull_request_template.md`).

## License

MIT. See [LICENSE](LICENSE).

[releases]: https://github.com/prestomation/ha-home-keeper-library/releases
[release-shield]: https://img.shields.io/github/release/prestomation/ha-home-keeper-library.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/prestomation/ha-home-keeper-library.svg?style=for-the-badge
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[hacs-validation-shield]: https://github.com/prestomation/ha-home-keeper-library/actions/workflows/hacs.yml/badge.svg
[hacs-validation]: https://github.com/prestomation/ha-home-keeper-library/actions/workflows/hacs.yml
