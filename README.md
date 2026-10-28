# orbi-e2e-2609260042

这是 Orbi beta 的端到端测试仓库

![CI](https://github.com/xqliu/orbi-e2e-2609260042/actions/workflows/ci.yml/badge.svg)

Orbi beta e2e from signup (2026-09-26)

本仓库是 Orbi beta 的端到端（e2e）测试仓库：它没有应用服务，产物是 README、Issue 模板与一个最小的 Stripe 付款入口，并由 CI 在每个 pull request 上运行内容检查。

## 请勿提交 PR

本仓库是 Orbi beta 的端到端（e2e）测试仓库，只服务于 Orbi 自身的自动化回归验证。
它不是应用项目，也不接受外部贡献：请勿向本仓库提交 pull request（PR）。

## 如何贡献

欢迎提 Issue！本仓库不接受 pull request；要贡献，请通过 Issue 提出：

1. 在本仓库的 Issues 中新建一个 Issue。
2. 选择 `User outcome` 模板（模板文件为 `.github/ISSUE_TEMPLATE/user-outcome.md`），
   先在正文开头的 `## 优先级` 里写明优先级（`高` / `中` / `低` 三档，`高` 最高，
   可留空），再按模板填写五节：`## User outcome`（用户可见的结果）、`## Preconditions`
   （前置条件与真实入口命令）、`## Steps to reproduce`（可照做的复现步骤）、
   `## Acceptance`（成功路径与失败路径）、`## Evidence`（真实入口与可复现的证据）。
3. 要提功能建议时，选择 `功能建议` 模板（模板文件为
   `.github/ISSUE_TEMPLATE/feature-request.md`），填写 `## 想解决的问题` 与
   `## 期望的效果` 两节。
4. 维护者据此实现变更，并在 CI 检查通过后合并到 `main`。

提交前，请先在仓库根目录运行 `python -m pytest`，测试全部通过后再提 PR。

遇到问题或需要咨询，可发邮件至 support@orbi.build。
有问题可以在 Issue 里问。

## 反馈问题

遇到问题或有疑问时，请先搜索一下仓库里已有的 Issue，确认没有相同的问题后再新建，
避免重复提问；新建时请使用 [Issue 模板](.github/ISSUE_TEMPLATE/user-outcome.md)。

## Tests

`.github/workflows/ci.yml` runs the repository content checks and the
Stripe payment tests on pull requests and on `main`:

```sh
python -m pip install pytest stripe
python -m pytest
```

CI 会在每个 PR 上运行这些检查。

## Run the tests locally

在仓库根目录执行（需要 Python 3，并先安装测试依赖
`python3 -m pip install pytest stripe`）：

```sh
python3 -m unittest discover -s tests -v
```

测试用例是 pytest 风格的函数，`unittest` 收集不到它们，所以上面这条命令并不会
真正跑测试：依赖装好后它报告 `Ran 0 tests`、以 `NO TESTS RAN` 结束并返回退出码
5；依赖没装时它报 `ModuleNotFoundError: No module named 'pytest'`（或
`'stripe'`）。这两种结果都说明测试没有运行，不等于测试通过。要在本地跑完全部
测试，改用与 CI 相同的命令，pytest 汇总报告全部通过（例如 `44 passed`，没有
`failed`）即成功：

```sh
python3 -m pytest
```

## Running the content checks locally

The checks need Python 3, `pytest` and the official `stripe` SDK, and the
commands below run the same checks as CI. Run them in this order: get the
repository, confirm Python 3, install the dependencies, run the checks.

```sh
git clone https://github.com/xqliu/orbi-e2e-2609260042.git
cd orbi-e2e-2609260042
python --version
python -m pip install pytest stripe
python -m pytest
```

`python --version` must print Python 3 (for example `Python 3.12.3`); if it
prints a Python 2 version such as `Python 2.7.18`, or the command fails with
`command not found`, this machine has no Python 3: install it from
https://www.python.org/downloads/ (or with your system package manager), then
continue with `python -m pip install pytest stripe` and run `python -m pytest`
until the summary reports that every test passed (for example
`20 passed in 5.83s`, with no `failed`).

`python -m pytest` runs the repository content checks
(`tests/test_repository_content.py`) and the Stripe payment tests
(`tests/test_stripe_payments.py`); every test must pass (the pytest summary
must report no `failed`).

If `pytest` or `stripe` is not installed, `python -m pytest` fails with
`No module named pytest` (or `No module named stripe`); install both with
`python -m pip install pytest stripe` and run `python -m pytest` again.

## Stripe 付款（live 验证）

本仓库带一个最小的 Stripe 付款入口，只使用 live 密钥；密钥从不入库、也不进命令
行参数，只从环境变量 `STRIPE_LIVE_SECRET_KEY` 读取。

1. 在 Stripe 账户里预先创建一个支付方式 `pm_...`（卡号不进 CI、不落盘），并把
   live 密钥 `sk_live_...` 存成受保护 GitHub Actions 环境 `stripe-live` 的环境
   secret `STRIPE_LIVE_SECRET_KEY`。该环境必须开启 Required reviewers，只有人工
   批准后才会真正扣款。如果这个支付方式挂在某个 Customer 下，再记下它的
   `cus_...`（Stripe 要求同时提供 customer id）。
2. 真实收款入口（Stripe Checkout 托管页）：用 live 密钥创建结账页并打开它付款：

   ```sh
   STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments checkout --amount 100 --currency cny
   ```

   命令打印 `checkout_session id=cs_... url=https://checkout.stripe.com/...`；
   在浏览器里完成付款后，Stripe Dashboard → Payments 里出现这笔 live 收款。
3. 受保护的真实验证运行：在 GitHub Actions 里对 `CI` 工作流手动 `Run workflow`，
   在 `live payment verification` 任务里填步骤 1 的 `pm_...`（若支付方式挂在
   Customer 下，同时填 `cus_...`），并批准 `stripe-live` 环境。运行日志里出现
   `payment_intent id=pi_... status=succeeded`，在 Stripe Dashboard 里按同一个
   `pi_...` 核对到记录。
4. 失败与修复：`STRIPE_LIVE_SECRET_KEY` 缺失时日志报出该环境变量名并以非零退出；
   密钥失效时日志报出 Stripe 的 `HTTP 401`。补上或轮换环境 secret、重新发起运行
   并批准即可，不需要改代码。

### 导出付款数据（export）

`export` 子命令把账户的 PaymentIntents、Refunds、Customers 写成文件；`--format`
决定写哪几种，不传时和以前一样两种都写，所以只要 CSV 时不必再手动删 JSON：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --format csv
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --format json
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --format both
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --customer cus_123 --format csv
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --email buyer@example.com --format csv
```

第一行只写 `payments-2026-10-28.csv`、`refunds-2026-10-28.csv`、
`customers-2026-10-28.csv`，第二行只写同名的 `.json`，第三行（以及不传
`--format` 时）两种都写，共六个文件。文件名里的日期是导出当天的 UTC 日期
（`YYYY-MM-DD`），所以哪天导出的文件一眼就能看出来，不同天导出的文件也不会
互相覆盖（同一天重复导出会覆盖同名文件）。文件写到
`--output-dir` 指定的目录，默认是 `export/`（已被 `.gitignore` 忽略）；
`--limit` 是每次列表请求的条数（1-100，默认 10），所有记录都会被导出。命令打印
`exported payments=... refunds=... customers=... to export/`。

CSV 的第一行是中文列名，打开 `payments-<日期>.csv` 就是
`编号,金额,币种,状态,创建时间,客户邮箱`；`refunds-<日期>.csv` 是
`编号,付款编号,金额,币种,状态,创建时间`，`customers-<日期>.csv` 是
`编号,邮箱,创建时间`。`客户邮箱` 列（Issue #239）取自付款所属 Customer 的
`email`，导出的 Customers 列表本来就要读取，所以不会多一次请求；对账时直接看到
是谁付的，不用再按 `cus_...` 去 `customers-<日期>.csv` 里查。付款没有 customer
（游客付款）、Customer 没有邮箱或该 customer 不在客户列表里时，这一格为空。
JSON 文件的 key 保持英文不变（payments 行多出 `customer_email` 键），已按英文
key 读取的脚本不用改。

只导出某个客户时传 `--customer cus_...`（第四行）：Stripe 的 PaymentIntents
列表按这个 `customer` 过滤，所以 `payments-<日期>.csv` 每一行都是该客户，并多出
一列 `客户`（表头变成 `编号,客户,金额,币种,状态,创建时间,客户邮箱`），值取自
每笔付款记录本身（因为列表已被过滤，它就是传入的这个
id）；退款列表本身没有 customer 过滤，命令只保留那些
`payment_intent` 属于该客户付款的退款。不传 `--customer` 时没有 `客户` 列
（`客户邮箱` 列始终存在），导出账户全部记录。`customers-<日期>.csv` 仍是账户的
客户列表，不随 `--customer` 收窄。

只导出某个客户邮箱的记录时传 `--email buyer@example.com`（第五行）：Stripe 的
Customers 列表按文档化的 `email` 条件过滤（精确匹配，大小写敏感），所以
`customers-<日期>.csv` 只剩这个邮箱的客户；再按这些客户的 `cus_...` 用
PaymentIntents 列表的 `customer` 条件读取付款，退款同样只保留 `payment_intent`
属于这些付款的记录。`payments-<日期>.csv` 保持原来的列（不因 `--email` 多出
`客户` 列），每行 `客户邮箱` 都是传入的地址。`--email` 与 `--customer` 二选一，
同时给出时命令直接报错。

失败与修复：`--format` 只接受 `csv`、`json`、`both`，填别的值时命令以退出码 2
结束并报 `argument --format: invalid choice: 'xml' (choose from 'csv', 'json',
'both')`，此时不会调用 Stripe、也不会创建目录；按提示改成这三档之一再运行。
`--customer` 传空字符串时命令以退出码 2 结束并报
`error: --customer must not be empty, got ''`，同样不会调用 Stripe、不会创建目录；
改成真实的 `cus_...` 后重跑。`--email` 传空字符串时报
`error: --email must not be empty, got ''`；邮箱在 Stripe 里找不到（或大小写和
Stripe 里的不一致）时命令以退出码 2 结束并报
`error: no Stripe customer has the email 'nobody@example.com'; the Customers list's email filter is an exact match, so copy the address from the Stripe dashboard and re-run`，
此时只查了一次 Customers 列表、没有写任何文件；按 Stripe Dashboard 里的拼写
重跑即可。`--email` 和 `--customer` 同时给出时报
`error: --email and --customer cannot be combined: pass the customer's email or its cus_... id, not both`，
去掉其中一个再运行。缺少 `STRIPE_LIVE_SECRET_KEY` 时同样以退出码 2
报出变量名，补上环境变量后重跑。

### 汇总收入（summary）

`summary` 子命令在终端按币种逐行打印付款总额、退款总额和净收入，最后再多打印
一行所有已打印币种的合计，金额带千分位、币种大写，每天看一眼即可，不用再打开
CSV 自己算：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary
```

每个币种一行（按币种代码排序），最后再打印一行 `合计`，例如：

```
EUR 付款 10.00 退款 0.00 净额 10.00
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,244.57 退款 1.00 净额 1,243.57
```

金额按 Stripe 的最小货币单位换算：两位小数币种（如 USD、EUR、CNY）除以 100，
零小数币种（如 JPY、KRW）按文档（<https://docs.stripe.com/currencies>）原样打印
整数；净额 = 付款 - 退款。`合计` 行的数值就是上面各行打印值之和（按打印出来的
数值相加：两位小数币种按分、零小数币种按整数，统一换算成两位小数后相加），所以
不用自己再加一遍；它始终在币种行之后打印。账户没有付款和退款时不打印任何行，
也就没有合计行。

只想看某一个币种时传 `--currency`（不区分大小写，例如 `usd` 或 `USD`）：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --currency usd
```

输出里只有 usd 那一行和合计行（其他币种不打印）：

```
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,234.57 退款 1.00 净额 1,233.57
```

这里的合计行只加总这一次打印出来的行，所以就是 usd 自己的数值。账户里没有该币种
的付款和退款时不打印任何行（也没有合计行）。不传 `--currency` 时与上面完全一致，
列出全部币种。

想把这份汇总同时导出成 CSV（拿去 Excel 对账）时加 `--csv`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --csv
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --csv --output-dir 对账
```

终端输出的汇总行与上面完全一致（包含合计行），合计行之后才多打印一行
`exported summary rows=2 to export/summary-2026-10-28.csv`（所以加 `--csv` 时
最后一行是这条文件提示，普通 `summary` 的最后一行就是合计行）。CSV 写到 `--output-dir`
指定的目录，默认是 `export/`（和 `export` 子命令同一个目录，已被 `.gitignore`
忽略）；文件名带导出当天的 UTC 日期（`YYYY-MM-DD`），所以不同天的汇总不会互相
覆盖（同一天重复导出会覆盖同名文件）。CSV 第一行是中文表头
`币种,付款,退款,净额`，之后每个币种一行（排序与打印顺序一致，不含合计行），
每一格就是上面打印行里的同一个值：

```
币种,付款,退款,净额
EUR,10.00,0.00,10.00
USD,"1,234.57",1.00,"1,233.57"
```

金额带千分位逗号时 CSV 自动加引号（`"1,234.57"`），所以用 Excel 打开时
`币种`、`付款`、`退款`、`净额` 各占一列，一个金额不会被拆成两列。`--currency usd`
与 `--csv` 一起用时，打印和 CSV 都只有 usd 那一行（打印再多一行 usd 的合计）；
账户没有付款和退款时终端不打印汇总行（也没有合计行），CSV 只写表头一行。
不加 `--csv` 时和以前一样只打印、不写文件。

失败与修复：`--currency` 传空字符串时命令以退出码 2 结束并报
`error: --currency must not be empty, got ''`，此时不会调用 Stripe；改成真实币种
代码（如 `usd`）后重跑。缺少 `STRIPE_LIVE_SECRET_KEY` 时命令以退出码 2 结束并报
`error: STRIPE_LIVE_SECRET_KEY is not set...`，补上环境变量后重跑；密钥失效时
报 Stripe 的 `HTTP 401`，轮换环境 secret 后重跑。加上 `--csv` 时，这些失败都发生在
写文件之前，不会留下空的或不完整的 CSV；补好配置重跑即可。

### 按月汇总退款（refunds-summary）

`refunds-summary` 子命令在终端按「退款创建月份（UTC）+ 币种」逐行打印退款笔数和
退款金额，不用再打开 CSV 自己筛：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments refunds-summary
```

命令不带参数，统计账户里的全部退款。每月每个币种一行（先按月份、再按币种代码
排序），例如 9 月有一笔 usd 退款 0.50、10 月有一笔 eur 退款 1.00 和两笔 usd
退款 1.00、2.50 时，完整输出就是这三行：

```
2026-09 usd 退款 1 笔 0.50
2026-10 eur 退款 1 笔 1.00
2026-10 usd 退款 2 笔 3.50
```

月份取退款记录 `created` 时间戳的 UTC 年月，币种保持 Stripe 返回的小写代码；金额
按与 `summary` 相同的最小货币单位规则换算（两位小数币种除以 100，JPY、KRW 等
零小数币种按文档原样打印，见 <https://docs.stripe.com/currencies>）。账户没有退款
记录时不打印任何行。

失败与修复：缺少 `STRIPE_LIVE_SECRET_KEY` 时命令以退出码 2 结束并报
`error: STRIPE_LIVE_SECRET_KEY is not set...`，补上环境变量后重跑；密钥失效时
报 Stripe 的 `HTTP 401`，轮换环境 secret 后重跑。

## FAQ

### Q：这个仓库是什么？为什么不接受 PR？

这是 Orbi beta 的端到端（e2e）测试仓库，没有应用服务，产物是 README、
Issue 模板与一个最小的 Stripe 付款入口。它只服务于 Orbi 自身的自动化回归
验证，不是应用项目，也不接受外部贡献，因此请勿提交 pull request（PR）；
要贡献请改为通过 Issue 提出。

### Q：怎么在本地运行内容检查？

需要 Python 3、`pytest` 与官方 `stripe` SDK，在仓库根目录执行与 CI 相同的
命令：

```sh
python -m pip install pytest stripe
python -m pytest
```

`python -m pytest` 会运行仓库内容检查（`tests/test_repository_content.py`）与
Stripe 付款测试（`tests/test_stripe_payments.py`），全部必须通过（pytest 汇总里
没有 `failed`）。

### Q：运行 `python -m pytest` 报 `No module named pytest` 怎么办？

说明当前 Python 环境没有安装 `pytest`。用 `python -m pip install pytest stripe`
安装后，重新运行 `python -m pytest` 即可。

### Q：草稿要多久？

一般 1 到 2 分钟

### Q：写草稿算不算用量？

算，计入本月 AI 用量

### Q：卡住了怎么办？

先修掉卡住的原因，再把 `ai-blocked` 换成 `ai-fix-needed`。

### Q：运营看板的时间是什么时区？

北京时间（UTC+8）

### Q：生产漂移告警是什么？

线上版本或数据库迁移不一致时会报。

本仓库用于 Orbi beta 端到端测试

最后更新于 2026-09-28
回归测试 2026-09-28
回归测试 v0.6.82
回归测试 v0.6.106
Copyright © 2026 xqliu
Wake test 10-05

## 营业时间与电话

- 营业时间：周一至周五 09:00–18:00（北京时间）
- 电话：+86 400-820-1234
- 邮箱：support@orbi.build

本仓库用于 Orbi Cloud 每次发版前的新用户全流程验收（v0.7.12，2026-10-07）

## 运行测试

在仓库根目录执行下面的命令，它会用 pytest 运行 `tests/` 下的全部测试
（`tests/test_repository_content.py` 与 `tests/test_stripe_payments.py`）：

```sh
python -m pytest
```

汇总报告里全部通过（没有 `failed`）才算成功；这条命令与 CI 工作流
`.github/workflows/ci.yml` 里 `Run tests` 步骤用的是同一个入口。如果命令报
`No module named pytest`，说明当前环境没有安装 pytest，这不是测试通过：先运行
`python -m pip install pytest stripe` 安装依赖，再重新执行 `python -m pytest`。

This repository is used for Orbi beta end-to-end checks (v0.7.28 promotion gate)
Beta regression: Gemini native protocol hotfix v0.7.40.
