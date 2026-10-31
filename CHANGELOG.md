# 更新日志

本文件记录本仓库的所有显著变更。

格式参照 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

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

### 变更

- `export` 子命令导出的 CSV 第一行改成中文列名：`payments-<日期>.csv` 是
  `编号,金额,币种,状态,创建时间`（`refunds-<日期>.csv`、
  `customers-<日期>.csv` 同样为中文）；JSON 的 key 保持英文。
- `export` 子命令写出的文件名带上导出当天的 UTC 日期，例如
  `payments-2026-10-28.csv`，不同天导出的文件不再互相覆盖。
- `export` 导出的 `payments-<日期>.csv` 新增 `客户邮箱` 列：值取自付款所属
  Customer 的邮箱，对账时直接看到是谁付的；付款没有 customer、Customer 没有
  邮箱时该格为空。JSON 的 payments 行相应多出 `customer_email` 键。

## [v0.6.106] - 2026-09-28

### 变更

- 回归测试 v0.6.106。

## [v0.6.82] - 2026-09-28

### 变更

- 回归测试 v0.6.82。
