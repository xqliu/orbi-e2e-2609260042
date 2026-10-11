# 贡献指南

本仓库不接受 pull request；要贡献，请通过 Issue 提出，详见 README 的「如何贡献」一节。

提问前先搜已有 Issue

提 PR 前先本地跑一遍测试

## Running the tests

The test runner is `pytest`. From the repository root, install it (the suite
also needs the official `stripe` SDK) and run every test:

```sh
python -m pip install pytest stripe
python -m pytest
```

`python -m pytest` runs the repository content checks
(`tests/test_repository_content.py`) and the Stripe payment tests
(`tests/test_stripe_payments.py`); the pytest summary must report no `failed`.

If `pytest` is not installed, `python -m pytest` fails with
`No module named pytest`. Install it with `python -m pip install pytest stripe`
and run `python -m pytest` again. The same repair applies when the message
names `stripe` instead.

See the README's
[Running the content checks locally](README.md#running-the-content-checks-locally)
section for the full local checklist used by CI.
