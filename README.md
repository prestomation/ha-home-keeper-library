# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/prestomation/ha-home-keeper-library/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| custom\_components/home\_keeper\_library/\_\_init\_\_.py            |       81 |        0 |        6 |        1 |     99% | 127-\>132 |
| custom\_components/home\_keeper\_library/api\_surface.py            |       91 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/backend\_i18n.py           |       51 |        1 |        8 |        1 |     97% |        76 |
| custom\_components/home\_keeper\_library/book\_lookup.py            |      110 |       10 |       28 |        7 |     88% |56, 61, 89, 92-\>exit, 113, 130-\>exit, 140, 147-148, 151-152, 165 |
| custom\_components/home\_keeper\_library/card.py                    |       78 |       20 |       28 |        7 |     71% |59, 61, 73-75, 77-78, 82, 95, 108, 115-126, 130, 150-151 |
| custom\_components/home\_keeper\_library/card\_resource.py          |       29 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/config\_flow.py            |       72 |        1 |       14 |        1 |     98% |       125 |
| custom\_components/home\_keeper\_library/const.py                   |       87 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/coordinator.py             |       62 |        0 |       10 |        1 |     99% | 115-\>113 |
| custom\_components/home\_keeper\_library/covers.py                  |      236 |       23 |       72 |       11 |     89% |89, 99, 109, 142, 157-159, 171-\>exit, 192, 207-208, 234, 261, 264, 270-272, 292-293, 320-321, 370, 379, 427 |
| custom\_components/home\_keeper\_library/csv\_io.py                 |      415 |        2 |      140 |        1 |     99% |  296, 491 |
| custom\_components/home\_keeper\_library/diagnostics.py             |       11 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/entity.py                  |       50 |        1 |        8 |        1 |     97% |        62 |
| custom\_components/home\_keeper\_library/events.py                  |       40 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/frontend\_assets.py        |       17 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/home\_keeper.py            |      135 |        5 |       34 |        2 |     96% |144, 259, 277-279 |
| custom\_components/home\_keeper\_library/import\_export.py          |      515 |        2 |      200 |        3 |     99% |326-\>324, 579-582, 724-\>726 |
| custom\_components/home\_keeper\_library/isbn.py                    |       54 |        0 |       16 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/loan\_sync.py              |      131 |       15 |       50 |       13 |     85% |79-\>exit, 97, 112, 121-123, 128-\>131, 140, 147, 151, 168-\>148, 181, 185-186, 198, 205, 212, 215 |
| custom\_components/home\_keeper\_library/loan\_tasks.py             |      104 |        0 |       36 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/models.py                  |      622 |        0 |      352 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/openlibrary.py             |      134 |        1 |       64 |        3 |     98% |131, 134-\>129, 142-\>141 |
| custom\_components/home\_keeper\_library/openlibrary\_account.py    |       51 |        6 |       12 |        3 |     86% |61, 91, 93-95, 102 |
| custom\_components/home\_keeper\_library/openlibrary\_client.py     |      143 |        6 |       42 |        6 |     94% |109, 156, 191-192, 200-\>exit, 217, 235-\>238, 241-\>239, 251 |
| custom\_components/home\_keeper\_library/openlibrary\_contribute.py |       62 |        0 |       24 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/people.py                  |       36 |        3 |       10 |        3 |     87% |40, 56, 63 |
| custom\_components/home\_keeper\_library/projections.py             |      189 |        1 |       88 |        1 |     99% |       360 |
| custom\_components/home\_keeper\_library/sensor.py                  |       75 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/services.py                |      563 |       18 |      154 |       14 |     96% |405-\>418, 411-412, 426-427, 431-\>430, 437, 500-501, 536-\>538, 576, 579, 678, 765-766, 769, 797, 843, 1053, 1082, 1084 |
| custom\_components/home\_keeper\_library/store.py                   |      513 |       31 |      152 |       27 |     91% |81, 118-\>exit, 134-135, 218, 242-\>244, 248, 275-\>277, 279, 294, 384, 396-\>398, 408-\>413, 439-\>441, 479-\>exit, 507, 587-591, 635, 680-\>694, 758, 766, 768-\>770, 823, 825-\>831, 832-835, 837, 867, 886-\>884, 892-\>889, 905-913 |
| custom\_components/home\_keeper\_library/todo.py                    |       73 |        9 |       14 |        3 |     86% |112, 132-133, 139, 144-145, 154, 157-158 |
| custom\_components/home\_keeper\_library/websocket\_api.py          |       79 |        6 |       12 |        2 |     91% |101-108, 124-125, 153-154 |
| custom\_components/home\_keeper\_library/wishlist.py                |      117 |        0 |       44 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/wishlist\_sync.py          |      105 |        7 |       28 |        3 |     92% |73-\>exit, 93-\>exit, 99, 109-111, 129-131 |
| **TOTAL**                                                           | **5131** |  **168** | **1650** |  **114** | **96%** |           |


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