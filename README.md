# orbi-e2e-2609260042

![CI](https://github.com/xqliu/orbi-e2e-2609260042/actions/workflows/ci.yml/badge.svg)

Orbi beta e2e from signup (2026-09-26)

本仓库是 Orbi beta 的端到端（e2e）测试仓库：它没有应用代码，产物是 README 与 Issue 模板，并由 CI 在每个 pull request 上运行内容检查。

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
3. 维护者据此实现变更，并在 CI 检查通过后合并到 `main`。

## Tests

`.github/workflows/ci.yml` runs the repository content checks on pull
requests and on `main`:

```sh
python -m pytest
```

本地运行前先装 pytest（`python -m pip install pytest`）。

CI 会在每个 PR 上运行这些检查。

## Running the content checks locally

The checks need Python 3 and `pytest`, and the commands below run the same
checks as CI. Run them in this order: get the repository, confirm Python 3,
install `pytest`, run the checks.

```sh
git clone https://github.com/xqliu/orbi-e2e-2609260042.git
cd orbi-e2e-2609260042
python --version
python -m pip install pytest
python -m pytest
```

`python --version` must print Python 3 (for example `Python 3.12.3`); if it
prints a Python 2 version such as `Python 2.7.18`, or the command fails with
`command not found`, this machine has no Python 3: install it from
https://www.python.org/downloads/ (or with your system package manager), then
continue with `python -m pip install pytest` and run `python -m pytest` until
the summary says `4 passed`.

`python -m pytest` runs `tests/test_repository_content.py`, whose four checks
must all pass (`4 passed` in the pytest summary).

If `pytest` is not installed, `python -m pytest` fails with
`No module named pytest`; install it with `python -m pip install pytest` and
run `python -m pytest` again.

## FAQ

### Q：这个仓库是什么？为什么不接受 PR？

这是 Orbi beta 的端到端（e2e）测试仓库，没有应用代码，产物是 README 与
Issue 模板。它只服务于 Orbi 自身的自动化回归验证，不是应用项目，也不接受
外部贡献，因此请勿提交 pull request（PR）；要贡献请改为通过 Issue 提出。

### Q：怎么在本地运行内容检查？

需要 Python 3 与 `pytest`，在仓库根目录执行与 CI 相同的命令：

```sh
python -m pip install pytest
python -m pytest
```

`python -m pytest` 会运行 `tests/test_repository_content.py`，其中四条检查
必须全部通过（pytest 汇总输出为 `4 passed`）。

### Q：运行 `python -m pytest` 报 `No module named pytest` 怎么办？

说明当前 Python 环境没有安装 `pytest`。用 `python -m pip install pytest`
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

本仓库用于 Orbi Cloud 每次发版前的新用户全流程验收（v0.7.12，2026-10-07）
