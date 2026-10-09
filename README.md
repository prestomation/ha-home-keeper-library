# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| custom\_components/home\_keeper\_library/\_\_init\_\_.py        |       81 |        0 |        6 |        1 |     99% | 127-\>132 |
| custom\_components/home\_keeper\_library/api\_surface.py        |       91 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/backend\_i18n.py       |       51 |        1 |        8 |        1 |     97% |        76 |
| custom\_components/home\_keeper\_library/book\_lookup.py        |      105 |       10 |       26 |        6 |     88% |55, 60, 88, 91-\>exit, 112, 131, 138-139, 142-143, 156 |
| custom\_components/home\_keeper\_library/card.py                |       78 |       20 |       28 |        7 |     71% |59, 61, 73-75, 77-78, 82, 95, 108, 115-126, 130, 150-151 |
| custom\_components/home\_keeper\_library/card\_resource.py      |       29 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/config\_flow.py        |       43 |        0 |       10 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/const.py               |       81 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/coordinator.py         |       44 |        0 |        6 |        1 |     98% |   84-\>82 |
| custom\_components/home\_keeper\_library/covers.py              |      187 |       15 |       56 |       10 |     90% |86, 96, 106, 139, 154-156, 168-\>exit, 189, 193, 204-205, 231, 286, 295, 343 |
| custom\_components/home\_keeper\_library/csv\_io.py             |      415 |        2 |      140 |        1 |     99% |  296, 491 |
| custom\_components/home\_keeper\_library/diagnostics.py         |       10 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/entity.py              |       50 |        1 |        8 |        1 |     97% |        62 |
| custom\_components/home\_keeper\_library/events.py              |       38 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/frontend\_assets.py    |       17 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/home\_keeper.py        |      135 |        5 |       34 |        2 |     96% |143, 255, 273-275 |
| custom\_components/home\_keeper\_library/isbn.py                |       54 |        0 |       16 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/loan\_sync.py          |      131 |       15 |       50 |       13 |     85% |79-\>exit, 97, 112, 121-123, 128-\>131, 140, 147, 151, 168-\>148, 181, 185-186, 198, 205, 212, 215 |
| custom\_components/home\_keeper\_library/loan\_tasks.py         |      104 |        0 |       36 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/models.py              |      576 |        0 |      340 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/openlibrary.py         |      134 |        1 |       64 |        3 |     98% |130, 133-\>128, 141-\>140 |
| custom\_components/home\_keeper\_library/openlibrary\_client.py |      105 |        4 |       34 |        5 |     94% |125-126, 145-\>148, 151-\>149, 155, 164 |
| custom\_components/home\_keeper\_library/people.py              |       36 |        3 |       10 |        3 |     87% |40, 56, 63 |
| custom\_components/home\_keeper\_library/projections.py         |      163 |        1 |       64 |        1 |     99% |       319 |
| custom\_components/home\_keeper\_library/sensor.py              |       75 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/services.py            |      407 |       13 |      106 |        9 |     96% |366-\>379, 372-373, 387-388, 392-\>391, 398, 461-462, 497-\>499, 529, 616-617, 620, 648, 694 |
| custom\_components/home\_keeper\_library/store.py               |      497 |       31 |      146 |       26 |     91% |80, 117-\>exit, 133-134, 217, 241-\>243, 247, 274-\>276, 278, 293, 383, 395-\>397, 407-\>412, 449-\>exit, 477, 557-561, 605, 650-\>664, 728, 736, 738-\>740, 793, 795-\>801, 802-805, 807, 837, 856-\>854, 862-\>859, 875-883 |
| custom\_components/home\_keeper\_library/todo.py                |       73 |        9 |       14 |        3 |     86% |112, 132-133, 139, 144-145, 154, 157-158 |
| custom\_components/home\_keeper\_library/websocket\_api.py      |       79 |        6 |       12 |        2 |     91% |101-108, 124-125, 152-153 |
| custom\_components/home\_keeper\_library/wishlist.py            |      117 |        0 |       44 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/wishlist\_sync.py      |      105 |        9 |       28 |        4 |     90% |71-72, 73-\>exit, 93-\>exit, 99, 109-111, 129-131 |
| **TOTAL**                                                       | **4111** |  **146** | **1290** |   **99** | **95%** |           |


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