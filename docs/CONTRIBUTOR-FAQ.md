# Contributor FAQ

本页回答新贡献者最常问的三个问题，涉及的完整说明见 [CONTRIBUTING.md](../CONTRIBUTING.md)
与 [README.md](../README.md)。术语（如 pytest、e2e）见 [术语表](GLOSSARY.md)。

## Q：这个仓库接受 pull request 吗？

不接受。本仓库是 Orbi beta 的端到端（e2e）测试仓库，不接受 pull request，
要贡献请通过 Issue 提出（详见 [CONTRIBUTING.md](../CONTRIBUTING.md) 的说明）。

1. 在本仓库的 Issues 中新建 Issue。
2. 用 `User outcome` 模板（`.github/ISSUE_TEMPLATE/user-outcome.md`）填写五节：
   `## User outcome`、`## Preconditions`、`## Steps to reproduce`、`## Acceptance`、
   `## Evidence`。
3. 想提功能建议时用 `功能建议` 模板
   （`.github/ISSUE_TEMPLATE/feature-request.md`），填写 `## 想解决的问题` 与
   `## 期望的效果` 两节。

维护者据此实现变更，并在 CI 检查通过后合并到 `main`。

## Q：怎么在本地跑测试？

在仓库根目录执行与 CI 相同的命令：

```sh
python -m pip install pytest stripe
python -m pytest
```

`python -m pytest` 会运行仓库内容检查（`tests/test_repository_content.py`）与
Stripe 付款测试（`tests/test_stripe_payments.py`）；最后一行是形如
`181 passed in 63.93s` 的汇总，且没有 `failed` 就表示全部通过。

## Q：运行 `python -m pytest` 报 `No module named pytest` 怎么办？

说明当前 Python 环境没有安装 `pytest`（报 `No module named stripe` 时同理，
缺的是官方 `stripe` SDK）。用 `python -m pip install pytest stripe` 安装依赖，
再重新运行 `python -m pytest` 即可。安装后仍失败，请把完整输出贴到 Issue 里，
见 [SUPPORT.md](SUPPORT.md) 的求助渠道。
