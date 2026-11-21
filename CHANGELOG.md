# 更新日志

本文件记录本仓库的所有显著变更。

格式参照 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## 未发布

暂无

## [Unreleased]

### 新增

- 新增更新日志 `CHANGELOG.md`，采用 Keep a Changelog 格式。
- 在 `User outcome` Issue 模板中新增 `## Steps to reproduce` 小节，
  供提交者填写可照做的复现步骤。
- 在 README 中新增联系邮箱 `support@orbi.build`。
- 新增 Stripe live 付款入口 `stripe_payments.py`：`checkout` 子命令创建
  Checkout 托管结账页，`verify` 子命令用预先创建的支付方式完成一笔真实扣款。
- `CI` 工作流新增手动触发、需人工批准 `stripe-live` 环境的
  `live payment verification` 任务。
- 新增 `功能建议` Issue 模板 `.github/ISSUE_TEMPLATE/feature-request.md`，
  含 `## 想解决的问题` 与 `## 期望的效果` 两节。
- 新增 `summary` 子命令：按币种逐行打印付款总额、退款总额和净收入，金额带
  千分位、币种大写。
- `export` 子命令新增 `--customer cus_...`：只导出该客户的付款和退款，
  `payments.csv` 多出一列 `customer`；不传时导出内容与以前一致。
- `export` 子命令新增 `--email <邮箱>`：只导出该邮箱客户的记录，
  `payments`、`refunds`、`customers` 三个导出文件都只含这些客户的记录；
  邮箱按 Stripe Customers 列表的精确过滤匹配，找不到时报出该邮箱并以退出码 2 结束，
  不写任何文件。
- 新增 `refunds-summary` 子命令：按 ISO 周（UTC，周一至周日）和币种逐行打印退款
  笔数与退款金额，例如 `2026-W44 usd 退款 2 笔 3.50`，各周行加起来就是全部退款。
- `summary` 子命令新增 `--currency usd`：输出只包含该币种那一行；不传时和
  以前一样列出全部币种。
- `summary` 子命令新增 `--csv`：打印汇总行的同时把它们写成
  `summary-<日期>.csv`（表头 `币种,付款,退款,净额`，每个汇总字段一列，Excel
  打开即可对账），默认落在 `export/`，`--output-dir` 可改目录；不加 `--csv`
  时和以前一样只打印、不写文件。
- `summary` 子命令在币种行之后多打印一行 `合计`，数值等于上面打印的各币种
  值之和，例如 `合计 付款 1,244.57 退款 1.00 净额 1,243.57`。
- `summary` 子命令新增 `--by-month`：按「月份（UTC）+ 币种」分组打印付款、退款和
  净额（例如 `2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57`），最后仍是一行
  合计；与 `--csv` 一起用时 CSV 多一列 `月份`。
- 顶层新增 `--version` 参数：`python -m stripe_payments --version` 打印当前版本号
  （如 `stripe_payments 0.6.106`）并以退出码 0 结束；不传时其他子命令行为不变。
- `summary` 子命令新增 `--quiet`：每个币种只打印一行「币种 + 净额」
  （如 `USD 1,233.57`），不打印 `付款`、`退款` 两列和 `合计` 行；与
  `--currency`、`--by-month` 可以一起用，`--csv` 仍写出与以前相同的内容；
  不传时输出与以前完全一致。
- `summary` 子命令新增 `--top N`：只打印净额最大的 N 个币种（按净额从大到小
  排序，例如 `summary --top 2`），`合计` 行只加总打印出来的行；不传时输出与
  以前完全一致。
- `summary` 子命令新增 `--days N`：只统计最近 N×24 小时内（按记录 `created`，
  含边界，如 `summary --days 30`）的付款和退款，通过 Stripe 列表的
  `created[gte]` 过滤参数只读取这个时间段；与 `--by-month`、`--currency`、
  `--quiet`、`--top`、`--csv` 组合时也只看到窗口内记录；不传时输出与以前完全一致。
- `summary` 子命令新增 `--by-customer`：按「客户（`cus_...`）+ 币种」分组打印付款、
  退款和净额（例如 `cus_alpha USD 付款 1,234.57 退款 1.00 净额 1,233.57`），退款按
  其 `payment_intent` 归到那笔付款的客户，没有客户的付款归到 `（未归属客户）` 一行；
  与 `--csv` 一起用时 CSV 多一列 `客户`，与 `--by-month`、`--currency`、`--quiet`、
  `--top`、`--days` 可组合；不传时输出与以前完全一致。
- `summary` 子命令在 `合计` 行之后多打印一行 `总笔数`（例如 `总笔数 4`），
  数值是上面打印行背后的付款 + 退款记录条数；与 `合计` 行一样只数这次打印出来的
  行（所以 `--currency`、`--top`、`--days` 过滤和分组时每条记录只算一次），
  `--quiet` 时与 `合计` 行一样不打印；原有输出内容不变，只是末尾多这一行。
- `summary` 子命令在 `总笔数` 行之后多打印一行 `平均金额`（例如 `平均金额 310.89`），
  数值是 `合计` 行的 `净额` 除以 `总笔数`（四舍五入到分，负数保留负号），
  所以不用自己拿计算器除一遍；与 `合计` 行一样只统计这次打印出来的行，
  `--quiet` 或没有打印行时与 `合计` 行一样不打印；原有输出内容不变，只是末尾
  多这一行。
- `summary` 子命令在 `平均金额` 行之后多打印一行 `最大单笔金额`
  （例如 `最大单笔金额 1,234.57`），数值是这次打印出来的行背后的付款和退款记录里
  金额最大的一笔（退款按它的正数金额参与比较），金额按与 `合计` 行相同的单位统一
  成两位小数，所以不用再翻 CSV 找最大的一笔；与 `合计` 行一样只统计这次打印出来的
  行，`--quiet` 或没有打印行时与 `合计` 行一样不打印；原有输出内容不变，只是末尾
  多这一行。
- `summary` 子命令在 `最大单笔金额` 行之后多打印一行 `最小单笔金额`
  （例如 `最小单笔金额 0.01`），数值是这次打印出来的行背后的付款和退款记录里
  金额最小的一笔（退款按它的正数金额参与比较），金额按与 `合计` 行相同的单位统一
  成两位小数，所以不用再翻 CSV 找最小的一笔；与 `合计` 行一样只统计这次打印出来的
  行，`--quiet` 或没有打印行时与 `合计` 行一样不打印；原有输出内容不变，只是末尾
  多这一行。
- `summary` 子命令新增 `--since YYYY-MM-DD` / `--until YYYY-MM-DD`：只统计
  `created`（UTC）落在这段日期窗口内的付款和退款（`--since` 从当天 00:00:00Z 开始、
  `--until` 到当天 23:59:59Z 结束，两端都含，如
  `summary --since 2026-09-01 --until 2026-09-30`），窗口通过 Stripe 列表的
  `created[gte]` / `created[lte]` 下推；与 `--by-month`、`--by-customer`、
  `--currency`、`--quiet`、`--top`、`--csv` 组合时也只看到窗口内记录；日期非法或
  `--since` 晚于 `--until` 时以退出码 2 结束且不调用 Stripe、不写 CSV。
- `export` 子命令新增 `--since YYYY-MM-DD` / `--until YYYY-MM-DD`：只导出
  `created`（UTC）落在这段日期窗口内的记录（`--since` 从当天 00:00:00Z 开始、
  `--until` 到当天 23:59:59Z 结束，两端都含，如
  `export --since 2026-09-01 --until 2026-09-30 --format csv`），三个列表都通过
  Stripe 的 `created[gte]` / `created[lte]` 过滤参数下推，文件和末行计数都只覆盖
  窗口内记录；两个参数可只传一个；日期非法或 `--since` 晚于 `--until` 时以退出码 2
  结束且不调用 Stripe、不创建 `--output-dir`；不传时导出内容与以前完全一致。
- `refunds-summary` 子命令新增 `--since YYYY-MM-DD` / `--until YYYY-MM-DD`：只统计
  `created`（UTC）落在这段日期窗口内的退款（`--since` 从当天 00:00:00Z 开始、
  `--until` 到当天 23:59:59Z 结束，两端都含，如
  `refunds-summary --since 2026-09-01 --until 2026-09-30`），周标签仍按退款的
  `created` 算 ISO 周、行格式不变，所以窗口只决定哪些退款被计入——同一周里窗口外的
  退款不出现在该周的行里；窗口通过 Refunds 列表的 `created[gte]` / `created[lte]`
  下推，加 `--csv` 时 CSV 也只有窗口内的行；两个参数可只传一个；日期非法或
  `--since` 晚于 `--until` 时以退出码 2 结束且不调用 Stripe、不写 CSV；不传时输出与
  以前完全一致。
- `refunds-summary` 子命令在所有周/币种行之后新增一行
  `合计 退款 N 笔 X.XX`：N 和金额是这次打印的全部周行的和（与 `summary` 的
  `合计` 行同样按统一单位相加，零小数币种先换算成两位小数）；加 `--csv` 时合计行
  同样打印到终端、排在各周行之后，CSV 文件内容不变；账户没有退款时仍然什么都不打印。
- `refunds-summary` 子命令新增 `--currency usd`：只打印该币种的周退款行（单值、
  不分大小写，标签仍是 Stripe 返回的小写币种），例如
  `refunds-summary --currency usd` 只输出 usd 的周行、不打印 `合计` 行；过滤同时
  作用于 `--csv`，所以 CSV 的数据行和末行计数只含这些行；某个币种没有退款时不打印
  任何行、仍以退出码 0 结束；传空值（`--currency ''` 或全空白）时以退出码 2 结束并报
  `error: --currency must not be empty, got ''`，且不调用 Stripe、不写 CSV；不传时
  输出与以前完全一致。
- `summary` 子命令新增首行 `统计范围 <最早日期>..<最晚日期>`：日期取自这次真正计入
  统计的记录（`succeeded` 的付款和退款）里最早和最晚一笔的 `created`（UTC，
  `YYYY-MM-DD`，如 `统计范围 2026-09-05..2026-10-20`），所以不加任何日期选项时也
  打印真实范围；`--days`、`--since`、`--until` 打印窗口内记录的范围，`--currency`、
  `--top` 只挑行、不影响这一行，`--quiet` 和 `--csv` 写出的文件里都没有这一行；
  一笔记录都没有时只打印 `统计范围 无记录` 并以退出码 0 结束，其余输出内容与顺序不变。
- `export` 子命令新增 `--days N`：只导出最近 N×24 小时内（按记录 `created`，
  含边界，如 `export --days 30 --format csv`）创建的付款、退款和客户记录，窗口
  与校验和 `summary --days N`、`refunds-summary --days N` 完全一致，三个列表都通过
  Stripe 的 `created[gte]` 过滤参数下推，文件和末行计数都只覆盖窗口内记录；与
  `--since` 一起用时下界取两者更晚的那个，`--until` 仍到当天 23:59:59Z 结束；
  传 0、负数或非整数时以退出码 2 结束并报含 `--days 必须是正整数` 的错误行（如
  `error: --days must be positive, got 0 (--days 必须是正整数)`、
  `error: --days 必须是正整数，收到 'abc'`），且不调用 Stripe、不创建
  `--output-dir`、不写任何导出文件；不传时导出内容与以前完全一致。

### 变更

- `export` 子命令导出的 CSV 第一行改成中文列名：`payments-<日期>.csv` 是
  `编号,金额,币种,状态,创建时间`（`refunds-<日期>.csv`、
  `customers-<日期>.csv` 同样为中文）；JSON 的 key 保持英文。
- `export` 子命令写出的文件名带上导出当天的 UTC 日期，例如
  `payments-2026-10-28.csv`，不同天导出的文件不再互相覆盖。
- `export` 导出的 `payments-<日期>.csv` 新增 `客户邮箱` 列：值取自付款所属
  Customer 的邮箱，对账时直接看到是谁付的；付款没有 customer、Customer 没有
  邮箱时该格为空。JSON 的 payments 行相应多出 `customer_email` 键。
- `summary` 子命令只统计 Stripe 状态为 `succeeded` 的付款和退款：PaymentIntent
  与 Refund 中其他状态的记录（如 `requires_payment_method`、`requires_capture`、
  `processing`、`pending`、`failed`、`canceled`）不再计入付款、退款、净额、
  `合计`、`总笔数`、`平均金额`、`最大单笔金额`、`最小单笔金额`
  和 `--csv` 的每一格，所以汇总数字与 Stripe 里真正收到的钱一致；每一页记录都
  会被筛选，`--by-month`、`--by-customer`、`--quiet`、`--top`、`--currency`、
  `--days`、`--since/--until`、`--csv` 的任意组合都遵循同一规则；
  `refunds-summary` 当时仍统计所有状态的退款。
- `summary` 子命令不再在最后多打印一行 `记录 N 条`：它的数字与上面 `总笔数`
  永远相同，是重复的计数。删掉之后普通 `summary` 的最后一行就是
  `最小单笔金额 <金额>`（加 `--csv` 时最后一行仍是文件提示），与 README 的完整
  示例输出一致；`总笔数` 保留为唯一的记录条数，其余各行的数值、格式与顺序不变。
- `refunds-summary` 子命令只统计 Stripe 状态为 `succeeded` 的退款，与 `summary`
  的退款口径一致：`pending`、`failed`、`canceled` 等状态的退款不再计入周行、
  `合计` 行的笔数和金额，也不写进 `refunds-summary-<日期>.csv` 的数据行，所以同一个
  时间窗口下 `summary` 的退款金额与 `refunds-summary` 的合计、两份 CSV 的退款金额
  完全一致（零小数币种按 `summary` 的 `_summary_hundredths()` 口径换算后相等）；
  某一周只有非 `succeeded` 的退款时不打印该周，账户没有 `succeeded` 退款时不打印
  退款行和合计行、`--csv` 只写表头，退出码仍为 0；`--currency` 先按状态筛选再按
  币种筛选；`export` 仍导出所有状态的退款明细（带 `status` 列），行格式与 CSV 表头不变。
- `refunds-summary` 子命令新增 `--days N`：只统计最近 N×24 小时内（按退款
  `created`，含边界，如 `refunds-summary --days 30`）的 `succeeded` 退款，周行、
  `合计` 行和 `--csv` 数据行都只覆盖窗口内的退款，窗口通过 Refunds 列表的
  `created[gte]` 过滤参数只读取这个时间段；与 `--since` 一起用时下界取两者更晚
  的那个，`--until` 仍到当天 23:59:59Z 结束；与 `--currency`、`--csv`、
  `--output-dir` 可组合；传 0 或负数时以退出码 2 结束并报
  `error: --days must be positive, got 0`；不传时输出与以前完全一致。
- `summary --csv` 写出的文件名带上分组：不加分组时仍是 `summary-<日期>.csv`，
  `--by-month` 时是 `summary-by-month-<日期>.csv`，`--by-customer` 时是
  `summary-by-customer-<日期>.csv`，两者一起用时是
  `summary-by-customer-by-month-<日期>.csv`。同一天用不同分组导出会留下各自的
  文件，不再用另一种表头覆盖同名文件，最后一行
  `exported summary rows=N to <path>` 提示实际写出的那个文件；表头、列和
  `--quiet` 的行为不变。
- `summary` 和 `refunds-summary` 子命令在读到的记录上再校验一次日期窗口，与
  `export` 自 Issue #314 起的做法相同：即使列表响应带回了 `created` 早于
  `--since` 或晚于 `--until` 的记录，这些记录也不会进入任何币种行、`合计`、
  `总笔数`、`平均金额`、`最大单笔金额`、`最小单笔金额`、`统计范围`、退款周行
  或 `--csv` 写出的文件；`--days N` 的滚动截止时刻每次运行只取一次「现在」，
  所以下推的 `created[gte]` 与实际统计的记录永远用同一个时间点；不传日期
  选项时不过滤任何记录，输出与以前完全一致。

## [v0.6.106] - 2026-09-28

### 变更

- 回归测试 v0.6.106。

## [v0.6.82] - 2026-09-28

### 变更

- 回归测试 v0.6.82。
