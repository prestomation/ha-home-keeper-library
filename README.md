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
| custom\_components/home\_keeper\_library/const.py                   |       85 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/coordinator.py             |       58 |        0 |       10 |        1 |     99% | 109-\>107 |
| custom\_components/home\_keeper\_library/covers.py                  |      187 |       14 |       56 |        9 |     91% |86, 96, 106, 139, 154-156, 168-\>exit, 189, 204-205, 231, 286, 295, 343 |
| custom\_components/home\_keeper\_library/csv\_io.py                 |      415 |        2 |      140 |        1 |     99% |  296, 491 |
| custom\_components/home\_keeper\_library/diagnostics.py             |       11 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/entity.py                  |       50 |        1 |        8 |        1 |     97% |        62 |
| custom\_components/home\_keeper\_library/events.py                  |       38 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/frontend\_assets.py        |       17 |        0 |        2 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/home\_keeper.py            |      135 |        5 |       34 |        2 |     96% |143, 255, 273-275 |
| custom\_components/home\_keeper\_library/isbn.py                    |       54 |        0 |       16 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/loan\_sync.py              |      131 |       15 |       50 |       13 |     85% |79-\>exit, 97, 112, 121-123, 128-\>131, 140, 147, 151, 168-\>148, 181, 185-186, 198, 205, 212, 215 |
| custom\_components/home\_keeper\_library/loan\_tasks.py             |      104 |        0 |       36 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/models.py                  |      595 |        0 |      350 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/openlibrary.py             |      134 |        1 |       64 |        3 |     98% |130, 133-\>128, 141-\>140 |
| custom\_components/home\_keeper\_library/openlibrary\_account.py    |       51 |        6 |       12 |        3 |     86% |61, 91, 93-95, 102 |
| custom\_components/home\_keeper\_library/openlibrary\_client.py     |      143 |        6 |       42 |        6 |     94% |109, 156, 191-192, 200-\>exit, 217, 235-\>238, 241-\>239, 251 |
| custom\_components/home\_keeper\_library/openlibrary\_contribute.py |       62 |        0 |       24 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/people.py                  |       36 |        3 |       10 |        3 |     87% |40, 56, 63 |
| custom\_components/home\_keeper\_library/projections.py             |      167 |        1 |       66 |        1 |     99% |       331 |
| custom\_components/home\_keeper\_library/sensor.py                  |       75 |        0 |        0 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/services.py                |      490 |       15 |      130 |       11 |     96% |386-\>399, 392-393, 407-408, 412-\>411, 418, 481-482, 517-\>519, 557, 560, 659, 746-747, 750, 778, 824 |
| custom\_components/home\_keeper\_library/store.py                   |      506 |       31 |      150 |       26 |     91% |80, 117-\>exit, 133-134, 217, 241-\>243, 247, 274-\>276, 278, 293, 383, 395-\>397, 407-\>412, 466-\>exit, 494, 574-578, 622, 667-\>681, 745, 753, 755-\>757, 810, 812-\>818, 819-822, 824, 854, 873-\>871, 879-\>876, 892-900 |
| custom\_components/home\_keeper\_library/todo.py                    |       73 |        9 |       14 |        3 |     86% |112, 132-133, 139, 144-145, 154, 157-158 |
| custom\_components/home\_keeper\_library/websocket\_api.py          |       79 |        6 |       12 |        2 |     91% |101-108, 124-125, 153-154 |
| custom\_components/home\_keeper\_library/wishlist.py                |      117 |        0 |       44 |        0 |    100% |           |
| custom\_components/home\_keeper\_library/wishlist\_sync.py          |      105 |        9 |       28 |        4 |     90% |71-72, 73-\>exit, 93-\>exit, 99, 109-111, 129-131 |
| **TOTAL**                                                           | **4430** |  **156** | **1384** |  **106** | **95%** |           |


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