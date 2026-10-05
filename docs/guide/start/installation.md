# Installation

Home Keeper Library is a custom integration that installs with [HACS](https://hacs.xyz/).
It requires Home Keeper.

## Install Home Keeper first

1. Install Home Keeper with HACS, as its
   [installation steps](https://github.com/prestomation/ha-home-keeper#installation) say.
2. Restart Home Assistant.
3. Add the Home Keeper integration in **Settings → Devices & services → Add
   integration**.

The Library tab needs Home Keeper version 0.30.0b2 or later.

## Install the library

1. In HACS, add this repository as a custom repository, with the category
   **Integration**: `https://github.com/prestomation/ha-home-keeper-library`.
2. Install **Home Keeper Library** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, and select **Home Keeper
   Library**.
4. Enter the currency of the prices and values of your books, such as `EUR` or `USD`.
   The default is the currency of Home Assistant.
5. Select **Submit**.

The Home Keeper panel then has a **Library** tab. Open it from the Home Keeper entry in
the sidebar.

To change the currency later, open **Settings → Devices & services → Home Keeper
Library** and select **Configure**.

## Setup messages

If Home Keeper is not ready, the setup stops with 1 of these messages:

| Message | What to do |
|---|---|
| Home Keeper Library requires Home Keeper. | Install Home Keeper from HACS, restart Home Assistant, then add Home Keeper Library again. |
| Add the Home Keeper integration first. | Add the Home Keeper integration, then add Home Keeper Library again. |
| Update Home Keeper to version 0.30.0b2 or later. | Update Home Keeper in HACS, restart Home Assistant, then add Home Keeper Library again. |

## Repair issues

If Home Keeper goes away after the setup, the library keeps its data. The card, the
entities and the services still work. **Settings → Repairs** shows 1 of these issues:

- **Home Keeper is not installed.** Install Home Keeper from HACS and restart Home
  Assistant.
- **Home Keeper is not set up.** Add or enable the Home Keeper integration.
- **Home Keeper is too old.** Update Home Keeper.

While the issue shows, the Library tab and the loan tasks are off. When Home Keeper is
ready again, the issue goes away. The tab and the tasks then come back with no restart.

## Data

The library is 1 JSON document in `.storage/home_keeper_library`. The covers are JPEG
files in `.storage/home_keeper_library/covers/`. Both are in each Home Assistant backup.
