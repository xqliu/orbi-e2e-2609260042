# orbi-e2e-2609260042

这是 Orbi beta 的端到端测试仓库

![CI](https://github.com/xqliu/orbi-e2e-2609260042/actions/workflows/ci.yml/badge.svg)

Orbi beta e2e from signup (2026-09-26)

本仓库是 Orbi beta 的端到端（e2e）测试仓库：它没有应用服务，产物是 README、Issue 模板与一个最小的 Stripe 付款入口，并由 CI 在每个 pull request 上运行内容检查。

运行测试：在仓库根目录执行 `python -m pytest`（与 CI 的 `Run tests` 步骤同一个命令，详见 [运行测试](#运行测试)）。

## 快速开始

想在本地跑测试，在仓库根目录执行下面这一条命令即可（第一次运行前先装依赖，
见下文[运行测试](#运行测试)一节）：

```sh
python -m pytest -q
```

测试全部通过时，最后一行会是形如 `181 passed in 63.93s` 的汇总，且没有 `failed`。

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
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --since 2026-09-01 --until 2026-09-30 --format csv
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

只想导出某一段日期（按 UTC 整天）的记录时加 `--since` 和 `--until`（第六行）：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments export --since 2026-09-01 --until 2026-09-30 --format csv
```

`--since` 从当天 00:00:00Z（含）开始，`--until` 到当天 23:59:59Z（含）结束，
所以两端都是整天、边界上的记录也会导出；两个参数可以只传一个，只传 `--since`
时没有上界，只传 `--until` 时没有下界。窗口通过 Stripe 列表的 `created[gte]` /
`created[lte]` 过滤参数下推，三个列表（PaymentIntents、Refunds、Customers）都只
读取这一时间段的记录，所以 `payments-<日期>.csv`、`refunds-<日期>.csv`、
`customers-<日期>.csv` 里不会出现窗口外的行，命令最后一行的计数也只数窗口内的
记录。例如账户里有一条 2026-08-31 的付款、一条 `created` 正好是
2026-09-01T00:00:00Z 的付款、一条 `created` 正好是 2026-09-30T23:59:59Z 的退款、
一条 2026-10-01 的付款，窗口内还有 2 个客户时，输出是：

```
exported payments=1 refunds=1 customers=2 to export/
```

`--since` / `--until` 可以和 `--customer`、`--email`、`--format`、`--limit`、
`--output-dir` 一起用，它们都只看到窗口内的记录；不传这两个参数时导出内容与以前
完全一致（整个账户）。窗口同样套在 Customers 列表上，所以客户的 `created` 落在
窗口外时不会出现在 `customers-<日期>.csv` 里，`payments-<日期>.csv` 的 `客户邮箱`
那一格也就为空（与上面「该 customer 不在客户列表里」同一种情况）；`--email`
搭配窗口时，如果该邮箱的客户本身创建在窗口外，命令会报
`error: no Stripe customer has the email ...`，这时改用 `--customer cus_...`
指定客户、把窗口只套在付款和退款上即可。

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
去掉其中一个再运行。`--since` / `--until` 传的不是 `YYYY-MM-DD` 日期时以退出码
2 结束并报 `error: --since must be a YYYY-MM-DD date, got '2026-13-01'`；
`--since` 晚于 `--until` 时报
`error: --until 2026-09-01 must not be before --since 2026-09-30`。这两种情况都
不会调用 Stripe、也不会创建 `--output-dir`，改成合法日期或正确顺序后重跑。缺少
`STRIPE_LIVE_SECRET_KEY` 时同样以退出码 2 报出变量名，补上环境变量后重跑。

### 汇总收入（summary）

`summary` 子命令在终端按币种逐行打印付款总额、退款总额和净收入，最后再多打印
一行所有已打印币种的合计、一行总笔数、一行平均金额、一行最大单笔金额和一行
最小单笔金额，金额带千分位、币种大写，每天看一眼即可，不用再打开 CSV 自己算：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary
```

每个币种一行（按币种代码排序），然后打印一行 `合计`，之后一行 `总笔数` 是这些行
背后的付款 + 退款记录条数，再后面一行 `平均金额` 是每笔记录的平均金额，然后一行
`最大单笔金额` 是这些记录里金额最大的一笔，最后一行 `最小单笔金额` 是金额最小的
一笔，例如：

```
EUR 付款 10.00 退款 0.00 净额 10.00
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,244.57 退款 1.00 净额 1,243.57
总笔数 4
平均金额 310.89
最大单笔金额 1,234.56
最小单笔金额 0.01
```

金额按 Stripe 的最小货币单位换算：两位小数币种（如 USD、EUR、CNY）除以 100，
零小数币种（如 JPY、KRW）按文档（<https://docs.stripe.com/currencies>）原样打印
整数；净额 = 付款 - 退款。`合计` 行的数值就是上面各行打印值之和（按打印出来的
数值相加：两位小数币种按分、零小数币种按整数，统一换算成两位小数后相加），所以
不用自己再加一遍；它始终在币种行之后打印。`总笔数` 行紧跟在 `合计` 行之后，
数值是上面这些行背后的记录条数（付款记录 + 退款记录各算一笔），所以不用再回
Stripe 数一遍。`平均金额` 行紧跟在 `总笔数` 行之后，数值是 `合计` 行的 `净额`
除以 `总笔数`（1,243.57 ÷ 4 = 310.8925，四舍五入到分后打印 310.89），所以不用
自己拿计算器除一遍；与 `合计` 行一样统一打印两位小数，负数保留负号。`最大单笔
金额` 行紧跟在 `平均金额` 行之后，数值是上面这些行背后的付款和退款记录里金额最大
的一笔（退款按它的正数金额参与比较，所以上面例子里最大的就是那笔 1,234.56 的
付款；1,234.57 是那两笔 usd 付款的和），金额按与 `合计` 行相同的单位统一成两位
小数，所以不用再翻 CSV 找最大的一笔。`最小单笔金额` 行紧跟在 `最大单笔金额` 行之
后，数值是上面这些行背后的付款和退款记录里金额最小的一笔（退款同样按它的正数
金额参与比较，所以上面例子里最小的就是那笔 0.01 的 usd 付款），金额也统一成两位
小数，所以不用再翻 CSV 找最小的一笔。账户没有付款和退款时不打印任何行，也就
没有合计行、总笔数行、平均金额行、最大单笔金额行和最小单笔金额行。

只想看某一个币种时传 `--currency`（不区分大小写，例如 `usd` 或 `USD`）：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --currency usd
```

输出里只有 usd 那一行、合计行、总笔数行、平均金额行、最大单笔金额行和最小单笔
金额行（其他币种不打印）：

```
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,234.57 退款 1.00 净额 1,233.57
总笔数 3
平均金额 411.19
最大单笔金额 1,234.56
最小单笔金额 0.01
```

这里的合计行只加总这一次打印出来的行，所以就是 usd 自己的数值；总笔数也只数
这些行背后的记录（两笔 usd 付款 1,234.56 和 0.01 + 一笔 usd 退款 1.00），其他
币种的记录不算在内；平均金额就是这一行的净额除以总笔数（1,233.57 ÷ 3 =
411.19），最大单笔金额是这些记录里最大的那一笔（就是那笔 1,234.56 的付款，
不是两笔付款相加的 1,234.57），最小单笔金额是这些记录里最小的一笔（就是那笔
0.01 的付款）。
账户里没有该币种的付款和退款时不打印任何行（也没有合计行、总笔数行、平均金额行、
最大单笔金额行和最小单笔金额行）。不传 `--currency` 时与上面完全一致，列出全部
币种。

想把这份汇总同时导出成 CSV（拿去 Excel 对账）时加 `--csv`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --csv
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --csv --output-dir 对账
```

终端输出的汇总行与上面完全一致（包含合计行、总笔数行、平均金额行、最大单笔
金额行和最小单笔金额行），最小单笔金额行之后才多打印一行
`exported summary rows=2 to export/summary-2026-10-28.csv`
（所以加 `--csv` 时最后一行是这条文件提示，普通 `summary` 的最后一行就是
最小单笔金额行）。CSV 写到
`--output-dir` 指定的目录，默认是 `export/`（和 `export` 子命令同一个目录，已被 `.gitignore`
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
与 `--csv` 一起用时，打印和 CSV 都只有 usd 那一行（打印再多一行 usd 的合计、
总笔数、平均金额、最大单笔金额和最小单笔金额）；账户没有付款和退款时终端不打印
汇总行（也没有合计行、总笔数行、平均金额行、最大单笔金额行和最小单笔金额行），
CSV 只写表头一行。
不加 `--csv` 时和以前一样只打印、不写文件。

想按月看汇总（对账时看每个月的付款和退款）时加 `--by-month`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --by-month
```

每个「月份 + 币种」一行（先按月份、再按币种代码排序），行格式与上面相同，只是
前面多一个月份；月份取记录 `created` 时间戳的 UTC 年月（`YYYY-MM`），付款按付款
记录归月、退款按退款记录归月，所以每组的值只包含该月份的记录。最后仍然只打印
一行 `合计`，数值是这次打印出来的所有月份行的和，之后是 `总笔数` 行（这些月份行
背后的记录总数，每条记录只算一次），然后是 `平均金额` 行（`合计` 的 `净额` 除以
总笔数），然后是 `最大单笔金额` 行（这些记录里最大的一笔），最后是 `最小单笔金额`
行（这些记录里最小的一笔）。例如 9 月有一笔 usd
付款 10.00、
一笔 jpy 付款 500、一笔 usd 退款 0.50 和一笔 eur 退款 2.00，10 月有一笔 eur 付款
10.00、两笔 usd 付款 1,234.56 和 0.01（合计 1,234.57）和一笔 usd 退款 1.00 时，
完整输出是：

```
2026-09 EUR 付款 0.00 退款 2.00 净额 -2.00
2026-09 JPY 付款 500 退款 0 净额 500
2026-09 USD 付款 10.00 退款 0.50 净额 9.50
2026-10 EUR 付款 10.00 退款 0.00 净额 10.00
2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,754.57 退款 3.50 净额 1,751.07
总笔数 8
平均金额 218.88
最大单笔金额 1,234.56
最小单笔金额 0.01
```

币种与不加 `--by-month` 时一样大写，金额规则也一样。`--currency usd` 可以和
`--by-month` 一起用，只打印 usd 的各月份行和它们的合计。`--by-month` 与 `--csv`
一起用时，CSV 第一列多出一列 `月份`（表头 `月份,币种,付款,退款,净额`），其余列
与上面相同：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --by-month --csv
```

```
月份,币种,付款,退款,净额
2026-09,EUR,0.00,2.00,-2.00
2026-09,JPY,500,0,500
2026-09,USD,10.00,0.50,9.50
2026-10,EUR,10.00,0.00,10.00
2026-10,USD,"1,234.57",1.00,"1,233.57"
```

文件与不加 `--by-month` 时同名（`summary-<date>.csv`，默认写到 `export/`），只是表头
多一列，所以同一天先跑 `summary --csv` 再跑 `summary --by-month --csv`（或反过来）
会用另一种表头覆盖同名文件；想同时留两份就传不同的 `--output-dir`。

不传 `--by-month` 时输出与上面的默认输出一致（每个币种一行 + 合计行 + 总笔数行 +
平均金额行 + 最大单笔金额行 + 最小单笔金额行）。

想按客户看汇总（对账时看每个客户贡献了多少）时加 `--by-customer`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --by-customer
```

每个「客户 + 币种」一行（先按客户、再按币种代码排序），行格式与上面相同，只是行首
多一个客户 id（`cus_...`），例如 `cus_alpha USD 付款 1,234.57 退款 1.00 净额 1,233.57`。
客户取付款记录上的 `customer`；退款记录没有客户字段，按退款的 `payment_intent` 归到
那笔付款的客户。没有客户的付款（guest 结账）和找不到对应付款的退款都归到
`（未归属客户）` 一行，所以各行加起来仍是整个账户的金额。最后仍然只打印一行
`合计`，数值是这次打印出来的所有客户行的和，之后是 `总笔数` 行（这些客户行背后
的记录总数），然后是 `平均金额` 行（`合计` 的 `净额` 除以总笔数），然后是
`最大单笔金额` 行，最后是 `最小单笔金额` 行。例如 cus_alpha
有一笔 usd 付款 1,234.57
和一笔 usd 退款 1.00、cus_beta 有一笔 eur 付款 10.00、另有一笔无客户的 usd 付款 5.00
和它的 usd 退款 0.50 时，完整输出是：

```
cus_alpha USD 付款 1,234.57 退款 1.00 净额 1,233.57
cus_beta EUR 付款 10.00 退款 0.00 净额 10.00
（未归属客户） USD 付款 5.00 退款 0.50 净额 4.50
合计 付款 1,249.57 退款 1.50 净额 1,248.07
总笔数 6
平均金额 208.01
最大单笔金额 1,234.57
最小单笔金额 0.50
```

`--by-customer` 与 `--csv` 一起用时，CSV 第一列多出一列 `客户`（表头
`客户,币种,付款,退款,净额`，其余与不加 `--by-customer` 时相同）：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --by-customer --csv
```

`--currency`（先按币种过滤）、`--quiet`（每行是「客户 + 币种 + 净额」）、`--top`、
`--days`（只统计窗口内的记录）和 `--by-month` 都可以和 `--by-customer` 一起用；
与 `--by-month` 一起时每行前面是「客户 + 月份」（如
`cus_alpha 2026-10 USD 付款 20.00 退款 1.00 净额 19.00`），CSV 表头是
`客户,月份,币种,付款,退款,净额`。不传 `--by-customer` 时输出与上面的默认输出一致
（每个币种一行 + 合计行 + 总笔数行 + 平均金额行 + 最大单笔金额行 + 最小单笔金额
行）。

只想看每个币种的净收入、不要付款和退款两列时加 `--quiet`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --quiet
```

每个币种只打印一行「币种 + 净额」，不再打印 `付款`、`退款` 两列，也不打印
`合计` 行、`总笔数` 行、`平均金额` 行、`最大单笔金额` 行和 `最小单笔金额` 行（所以
脚本直接取第二列就是净收入）：

```
EUR 10.00
USD 1,233.57
```

币种大写、金额带千分位，与不加 `--quiet` 时那一行的 `净额` 完全相同。
`--currency usd` 和 `--by-month` 照样可以和 `--quiet` 一起用：前者仍只打印该币种，
后者每行前面仍带月份（例如 `2026-10 USD 1,233.57`），合计行、总笔数行、平均
金额行、最大单笔金额行和最小单笔金额行同样不打印。
`--csv` 与 `--quiet` 一起用时文件照旧写成与不加 `--quiet` 时相同的内容，只是终端
不再打印那行文件提示。不传 `--quiet` 时输出与上面的默认输出一致（含合计行、
总笔数行、平均金额行、最大单笔金额行和最小单笔金额行）。

只想看净收入最大的几个币种时加 `--top N`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --top 2
```

只打印净额最大的 2 个币种，按净额从大到小排序（不传 `--top` 时仍按币种代码排序、
打印全部币种）：

```
USD 付款 1,234.57 退款 1.00 净额 1,233.57
EUR 付款 500.00 退款 0.00 净额 500.00
合计 付款 1,734.57 退款 1.00 净额 1,733.57
总笔数 4
平均金额 433.39
最大单笔金额 1,234.57
最小单笔金额 0.01
```

行格式与不加 `--top` 时完全相同（金额规则也一样），`合计` 行只加总这次打印出来的行，
`总笔数` 行也只数这些行背后的记录，`平均金额` 行同样是这些行的合计净额除以总笔数，
`最大单笔金额` 行同样是这些行背后的记录里最大的一笔，`最小单笔金额` 行同样是
这些记录里最小的一笔。
净额相同时按币种代码（`--by-month` 时按月份、再按币种代码）排序，所以同样的数据
总是打印同样的顺序；`--top` 大于账户里的币种数时打印全部币种。`--quiet`（每行只
留净额）、`--currency`（先按币种过滤再取最大的 N 行）、`--by-month`（按「月份 +
币种」行取净额最大的 N 行）和 `--csv`（CSV 只写选中的行）都可以和 `--top` 一起用。
不传 `--top` 时输出与上面的默认输出一致（每个币种一行 + 合计行 + 总笔数行 +
平均金额行 + 最大单笔金额行 + 最小单笔金额行）。

只想看最近 30 天的付款和退款时加 `--days N`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --days 30
```

只统计创建时间（`created`，UTC）在最近 N×24 小时内的付款和退款，更早的记录不参与
计算；时间窗从运行时刻往前推 N×24 小时，恰好落在边界上的记录（`created` 等于
截止时刻）仍算在窗口内。窗口通过 Stripe 列表的 `created[gte]` 过滤参数下推，所以
只读取这一时间段的记录。行格式与不加 `--days` 时完全相同，`合计` 行只加总窗口内
打印出来的行，`总笔数` 行也只数窗口内这些行背后的记录，`平均金额` 行同样是窗口内
这些行的合计净额除以总笔数，`最大单笔金额` 行同样是窗口内这些记录里最大的一笔，
`最小单笔金额` 行同样是窗口内这些记录里最小的一笔。例如最近 30 天有一笔 usd
付款 1,234.57、一笔 usd 退款 1.00 和一笔
eur 付款 10.00，而 31 天前还有一笔 usd 付款 99.99 时，输出是：

```
EUR 付款 10.00 退款 0.00 净额 10.00
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,244.57 退款 1.00 净额 1,243.57
总笔数 3
平均金额 414.52
最大单笔金额 1,234.57
最小单笔金额 1.00
```

只想看某一段日期（按 UTC 整天）的付款和退款时加 `--since` 和 `--until`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --since 2026-09-01 --until 2026-09-30
```

`--since` 从当天 00:00:00Z（含）开始，`--until` 到当天 23:59:59Z（含）结束，
所以两端都是整天、边界上的记录也算在窗口内；两个参数可以只传一个，只传 `--since`
时没有上界，只传 `--until` 时没有下界。窗口通过 Stripe 列表的 `created[gte]` /
`created[lte]` 过滤参数下推，所以只读取这一时间段的记录。行格式与不加这两个参数时
完全相同，币种行、`合计` 行、`总笔数` 行、`平均金额` 行、`最大单笔金额` 行和
`最小单笔金额` 行都只覆盖窗口内的记录。例如窗口内有 usd 付款 1,234.57、usd 退款
1.00 和 eur 付款 10.00，正好落在 2026-09-01 00:00:00Z 的 gbp 付款 2.50、正好落在
2026-09-30 23:59:59Z 的 eur 退款 0.25 也算在窗口内，8 月 31 日和 10 月 1 日的记录
不参与统计时，输出是：

```
EUR 付款 10.00 退款 0.25 净额 9.75
GBP 付款 2.50 退款 0.00 净额 2.50
USD 付款 1,234.57 退款 1.00 净额 1,233.57
合计 付款 1,247.07 退款 1.25 净额 1,245.82
总笔数 5
平均金额 249.16
最大单笔金额 1,234.57
最小单笔金额 0.25
```

`--since` / `--until` 可以和 `--by-month`（只对窗口内的记录分月）、
`--by-customer`、`--currency`、`--quiet`、`--top` 和 `--csv` 一起用，它们都
只看到窗口内的记录；和 `--days` 同时传时取两者的交集（窗口起点取较晚的一个）。
不传这两个参数时输出与上面的默认输出一致（统计整个账户）。

只想看最近 7 天时把 N 传成 7：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments summary --days 7
```

窗口从运行时刻往前推 7×24 小时，早于这个窗口的付款和退款不参与统计，命令照常打印
窗口内的行并以退出码 0 结束。

`--days` 可以和 `--by-month`（只对窗口内的记录分月）、`--currency`、`--quiet`、
`--top` 和 `--csv` 一起用，它们都只看到窗口内的记录。不传 `--days` 时输出与上面
的默认输出一致（统计整个账户，末尾同样有合计行、总笔数行、平均金额行、最大
单笔金额行和最小单笔金额行）。

失败与修复：`--currency` 传空字符串时命令以退出码 2 结束并报
`error: --currency must not be empty, got ''`，此时不会调用 Stripe；改成真实币种
代码（如 `usd`）后重跑。`--top` 传 0 或负数时同样以退出码 2 结束并报
`error: --top must be positive, got 0`，改成正整数（如 `--top 2`）后重跑。
`--days` 传 0 或负数时同样以退出码 2 结束并报
`error: --days must be positive, got 0`，改成正整数（如 `--days 30`）后重跑。
`--since` / `--until` 传的不是 `YYYY-MM-DD` 日期时以退出码 2 结束并报
`error: --since must be a YYYY-MM-DD date, got '2026-13-01'`；`--since` 晚于
`--until` 时报
`error: --until 2026-09-01 must not be before --since 2026-09-30`。这两种情况都
不会调用 Stripe、也不会写 CSV，改成合法日期或正确顺序后重跑。
缺少 `STRIPE_LIVE_SECRET_KEY` 时命令以退出码 2 结束并报
`error: STRIPE_LIVE_SECRET_KEY is not set...`，补上环境变量后重跑；密钥失效时
报 Stripe 的 `HTTP 401`，轮换环境 secret 后重跑。加上 `--csv` 时，这些失败都发生在
写文件之前，不会留下空的或不完整的 CSV；补好配置重跑即可。

### 按周汇总退款（refunds-summary）

`refunds-summary` 子命令在终端按「退款创建周（UTC，ISO 8601 周）+ 币种」逐行打印
退款笔数和退款金额，不用再打开 CSV 自己筛：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments refunds-summary
```

默认只打印、不写文件，统计账户里的全部退款。每周每个币种一行（先按周、再按币种代码
排序），例如 ISO 第 40 周有一笔 usd 退款 0.50、第 44 周有一笔 eur 退款 1.00 和两笔
usd 退款 1.00、2.50 时，完整输出就是这四行（最后一行是上面各周行的合计）：

```
2026-W40 usd 退款 1 笔 0.50
2026-W44 eur 退款 1 笔 1.00
2026-W44 usd 退款 2 笔 3.50
合计 退款 4 笔 5.00
```

合计行把上面每个打印值按 `summary` 的 `合计` 行同样的单位相加（两位小数币种
按原值，JPY、KRW 等零小数币种先换算成两位小数），给出这次打印的全部退款笔数和
金额；跨币种时也合成一行，不按币种拆分。

只想看某一段日期（按 UTC 整天）的退款时加 `--since` 和 `--until`：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments refunds-summary --since 2026-09-01 --until 2026-09-30
```

`--since` 从当天 00:00:00Z（含）开始，`--until` 到当天 23:59:59Z（含）结束，所以
两端都是整天、边界上的退款也算在窗口内；两个参数可以只传一个，只传 `--since` 时
没有上界，只传 `--until` 时没有下界。窗口通过 Refunds 列表的 `created[gte]` /
`created[lte]` 过滤参数下推，所以只读取这一时间段的退款。周标签仍由每条退款的
`created` 用 UTC ISO 8601 周算出，币种、金额换算和行格式与不加这两个参数时相同，
只是窗口外的退款不再出现在任何一行。例如 8 月 31 日有一笔 usd 退款 0.50、`created`
正好是 2026-09-30T23:59:59Z 的 eur 退款 1.00、10 月 1 日有一笔 usd 退款 2.50 时，
上面的命令只统计窗口内的那一笔（10 月 1 日的退款虽然也在 ISO 第 40 周，但不在窗口
内，所以不出现）：

```
2026-W40 eur 退款 1 笔 1.00
合计 退款 1 笔 1.00
```

加 `--csv` 时 CSV 也只有窗口内的行：同一份数据下上一条命令的 CSV 只有表头
`周,币种,退款笔数,退款金额` 和下面这一行，终端在退款行和合计行之后多打印
`exported refunds-summary rows=1 to export/refunds-summary-2026-10-28.csv`：

```
周,币种,退款笔数,退款金额
2026-W40,eur,1,1.00
```

不传这两个参数时输出与上面的默认输出一致（统计账户里的全部退款）。

加上 `--csv` 后，同样的行还会写成一个 CSV 文件，并在这些退款行之后多打印一行文件
提示，说明写到了哪里：

```sh
STRIPE_LIVE_SECRET_KEY=sk_live_... python -m stripe_payments refunds-summary --csv
```

```
2026-W40 usd 退款 1 笔 0.50
2026-W44 eur 退款 1 笔 1.00
2026-W44 usd 退款 2 笔 3.50
合计 退款 4 笔 5.00
exported refunds-summary rows=3 to export/refunds-summary-2026-10-28.csv
```

文件默认写到 `export/`（已被 `.gitignore` 忽略），想换目录就传 `--output-dir`
（例如 `--output-dir 对账`），和 `summary --csv` 的选项与默认值相同；文件名里的
日期是导出当天的 UTC 日期（`refunds-summary-<YYYY-MM-DD>.csv`）。CSV 第一行是中文
表头 `周,币种,退款笔数,退款金额`，之后每周每个币种一行，顺序与终端打印顺序一致；
金额带千分位逗号时自动加引号（`3.50` 不加引号，`1,234.57` 写成 `"1,234.57"`），
Excel 不会把它拆成两列（合计行只打印到终端，不写进 CSV 文件）：

```
周,币种,退款笔数,退款金额
2026-W40,usd,1,0.50
2026-W44,eur,1,1.00
2026-W44,usd,2,3.50
```

不加 `--csv` 时和以前完全一样：只打印、不写文件。

周取退款记录 `created` 时间戳的 UTC 所在 ISO 8601 周（周一至周日，用 Python 标准库
`datetime.isocalendar()` 计算），标签形如 `2026-W44`；跨年时用 ISO 周年份，所以每笔
退款只会落在一行里，所有行（以及最后一行的合计）的笔数和金额加起来就是账户的
全部退款。币种保持 Stripe 返回的小写代码；金额按与 `summary` 相同的最小货币单位
规则换算（两位小数币种除以 100，JPY、KRW 等零小数币种按文档原样打印，见
<https://docs.stripe.com/currencies>）。账户没有退款记录时不打印任何退款行，也就
没有合计行；此时加 `--csv` 的 CSV 只有表头一行，终端也只有
`exported refunds-summary rows=0 to ...` 这一行提示。

失败与修复：`--since` / `--until` 传的不是 `YYYY-MM-DD` 日期时以退出码 2 结束并报
`error: --since must be a YYYY-MM-DD date, got '2026-13-01'`（或
`error: --until must be a YYYY-MM-DD date, got '2026-02-30'`）；`--since` 晚于
`--until` 时报
`error: --until 2026-09-01 must not be before --since 2026-09-30`。这几种情况都在
发出任何 Stripe 请求之前失败，加 `--csv` 也不会创建目录或文件，改成合法日期或正确
顺序后重跑。缺少 `STRIPE_LIVE_SECRET_KEY` 时命令以退出码 2 结束并报
`error: STRIPE_LIVE_SECRET_KEY is not set...`，补上环境变量后重跑（加 `--csv` 时
不会创建目录或文件）；密钥失效时报 Stripe 的 `HTTP 401`，轮换环境 secret 后重跑。

### 查看版本（--version）

`--version` 是顶层参数，打印这个入口的版本号并以退出码 0 结束，用来确认一次运行
对应的是哪个版本：

```sh
python -m stripe_payments --version
```

输出一行 `stripe_payments <版本号>`，例如：

```
stripe_payments 0.6.106
```

版本号与 `CHANGELOG.md` 的最新发布版本一致。不传 `--version` 时，其他子命令
（`checkout`、`verify`、`export`、`summary`、`refunds-summary`）的行为和以前完全
一样；版本号本身不需要 live 密钥。

## 常见问题

### Q：导出的文件在哪里？

默认在仓库根目录（执行命令的目录）下的 `export/`：`export` 子命令把文件写到
`--output-dir` 指定的目录，不传时就是这个 `export/`（已被 `.gitignore` 忽略，
不会被误提交）。每次导出会写 `payments-<日期>`、`refunds-<日期>`、
`customers-<日期>` 三组文件，后缀是 `.csv` 和/或 `.json`（`--format` 决定）；
`summary --csv` 写的是 `summary-<日期>.csv`。文件名里的 `<日期>` 是导出当天的
UTC 日期（`YYYY-MM-DD`，例如 `payments-2026-10-28.csv`），所以不同天的导出
不会互相覆盖，同一天重复导出会覆盖同名文件。想换目录就传 `--output-dir`（例如
`--output-dir 对账`），文件就写到那个目录；命令最后一行
`exported payments=... refunds=... customers=... to export/` 也会打印出实际目录。

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
本项目以 MIT 许可证发布。
想贡献请先开一个 Issue 说明你的想法，确认后再动手。
