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
- 新增 `refunds-summary` 子命令：按月份和币种逐行打印退款笔数与退款金额，
  例如 `2026-10 usd 退款 2 笔 3.50`。
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
