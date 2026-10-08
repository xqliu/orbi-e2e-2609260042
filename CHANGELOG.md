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

## [v0.6.106] - 2026-09-28

### 变更

- 回归测试 v0.6.106。

## [v0.6.82] - 2026-09-28

### 变更

- 回归测试 v0.6.82。
