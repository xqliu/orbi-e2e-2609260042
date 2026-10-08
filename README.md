# orbi-e2e-2609260042

这是 Orbi beta 的端到端测试仓库

![CI](https://github.com/xqliu/orbi-e2e-2609260042/actions/workflows/ci.yml/badge.svg)

Orbi beta e2e from signup (2026-09-26)

本仓库是 Orbi beta 的端到端（e2e）测试仓库：它没有应用服务，产物是 README、Issue 模板与一个最小的 Stripe 付款入口，并由 CI 在每个 pull request 上运行内容检查。

## 请勿提交 PR

本仓库是 Orbi beta 的端到端（e2e）测试仓库，只服务于 Orbi 自身的自动化回归验证。
它不是应用项目，也不接受外部贡献：请勿向本仓库提交 pull request（PR）。

## 如何贡献

本仓库不接受 pull request；要贡献，请通过 Issue 提出：

1. 在本仓库的 Issues 中新建一个 Issue。
2. 选择 `User outcome` 模板（模板文件为 `.github/ISSUE_TEMPLATE/user-outcome.md`），
   先在正文开头的 `## 优先级` 里写明优先级（`高` / `中` / `低` 三档，`高` 最高，
   可留空），再按模板填写五节：`## User outcome`（用户可见的结果）、`## Preconditions`
   （前置条件与真实入口命令）、`## Steps to reproduce`（可照做的复现步骤）、
   `## Acceptance`（成功路径与失败路径）、`## Evidence`（真实入口与可复现的证据）。
   要提功能建议时，选择 `功能建议` 模板（模板文件为
   `.github/ISSUE_TEMPLATE/feature-request.md`），填写 `## 想解决的问题` 与
   `## 期望的效果` 两节。
3. 维护者据此实现变更，并在 CI 检查通过后合并到 `main`。

## Tests

`.github/workflows/ci.yml` runs the repository content checks and the
Stripe payment tests on pull requests and on `main`:

```sh
python -m pip install pytest stripe
python -m pytest
```

CI 会在每个 PR 上运行这些检查。

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
