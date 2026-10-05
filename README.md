# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| custom\_components/home\_keeper\_library/\_\_init\_\_.py        |       78 |        0 |        6 |        1 |     99% | 120-\>125 |
| custom\_components/home\_keeper\_library/api\_surface.py        |       91 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/backend\_i18n.py       |       56 |        6 |       12 |        2 |     88% |55, 58-59, 62, 90-91 |
| custom\_components/home\_keeper\_library/book\_lookup.py        |      105 |       10 |       26 |        6 |     88% |55, 60, 88, 91-\>exit, 112, 131, 138-139, 142-143, 156 |
| custom\_components/home\_keeper\_library/card.py                |       78 |       20 |       28 |        7 |     71% |59, 61, 73-75, 77-78, 82, 95, 108, 115-126, 130, 150-151 |
| custom\_components/home\_keeper\_library/card\_resource.py      |       29 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/config\_flow.py        |       43 |        0 |       10 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/const.py               |       81 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/coordinator.py         |       44 |        0 |        6 |        1 |     98% |   86-\>84 |
| custom\_components/home\_keeper\_library/covers.py              |      182 |       17 |       54 |       10 |     89% |86, 96, 102, 104, 131, 146-148, 160-\>exit, 174, 184-185, 187-188, 209, 264, 273, 321 |
| custom\_components/home\_keeper\_library/csv\_io.py             |      405 |        2 |      136 |        1 |     99% |  307, 489 |
| custom\_components/home\_keeper\_library/diagnostics.py         |       10 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/entity.py              |       50 |        1 |        8 |        1 |     97% |        62 |
| custom\_components/home\_keeper\_library/events.py              |       38 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/frontend\_assets.py    |       19 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/home\_keeper.py        |      138 |        7 |       36 |        2 |     95% |141, 154-155, 253, 271-273 |
| custom\_components/home\_keeper\_library/isbn.py                |       51 |        0 |       16 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/loan\_sync.py          |      130 |       15 |       50 |       13 |     84% |78-\>exit, 96, 111, 120-122, 127-\>130, 139, 146, 150, 167-\>147, 180, 184-185, 197, 204, 211, 214 |
| custom\_components/home\_keeper\_library/loan\_tasks.py         |      104 |        0 |       36 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/models.py              |      578 |        1 |      340 |        2 |     99% |621, 657-\>662 |
| custom\_components/home\_keeper\_library/openlibrary.py         |      134 |        1 |       64 |        3 |     98% |130, 133-\>128, 141-\>140 |
| custom\_components/home\_keeper\_library/openlibrary\_client.py |      105 |        4 |       34 |        5 |     94% |125-126, 145-\>148, 151-\>149, 155, 164 |
| custom\_components/home\_keeper\_library/people.py              |       36 |        3 |       10 |        3 |     87% |40, 56, 63 |
| custom\_components/home\_keeper\_library/projections.py         |      161 |        1 |       64 |        1 |     99% |       314 |
| custom\_components/home\_keeper\_library/sensor.py              |       74 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/services.py            |      407 |       13 |      108 |       10 |     96% |365-\>378, 371-372, 386-387, 391-\>390, 397, 460-461, 496-\>498, 528, 611-\>613, 617-618, 621, 649, 695 |
| custom\_components/home\_keeper\_library/store.py               |      498 |       38 |      148 |       26 |     89% |80, 117-\>exit, 130-131, 155-156, 218, 242-\>244, 248, 275-\>277, 279, 294, 384, 396-\>398, 406-410, 448-\>exit, 476, 556-560, 604, 649-\>663, 725, 733, 735-\>737, 790, 792-\>795, 796-799, 801, 831, 850-\>848, 856-\>853, 869-877 |
| custom\_components/home\_keeper\_library/todo.py                |       74 |       10 |       14 |        3 |     85% |58, 119, 139-140, 146, 151-152, 161, 164-165 |
| custom\_components/home\_keeper\_library/websocket\_api.py      |       81 |        6 |       14 |        2 |     92% |101-102, 118-119, 146-147 |
| custom\_components/home\_keeper\_library/wishlist.py            |      117 |        0 |       44 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/wishlist\_sync.py      |      104 |        9 |       28 |        4 |     90% |70-71, 72-\>exit, 92-\>exit, 98, 108-110, 128-130 |
| **TOTAL**                                                       | **4101** |  **164** | **1296** |  **103** | **95%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/prestomation/ha-home-keeper-library/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prestomation/ha-home-keeper-library/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fprestomation%2Fha-home-keeper-library%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.