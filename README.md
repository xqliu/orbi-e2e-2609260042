# orbi-e2e-2609260042
Orbi beta e2e from signup (2026-09-26)

本仓库是 Orbi beta 的端到端（e2e）测试仓库：它没有应用代码，产物是 README 与 Issue 模板，并由 CI 在每个 pull request 上运行内容检查。

## Tests

`.github/workflows/ci.yml` runs the repository content checks on pull
requests and on `main`:

```sh
python -m pytest
```

## Running the content checks locally

The checks need Python 3 and `pytest`, and the commands below run the same
checks as CI. From the repository root:

```sh
python -m pip install pytest
python -m pytest
```

`python -m pytest` runs `tests/test_repository_content.py`, whose four checks
must all pass (`4 passed` in the pytest summary).

If `pytest` is not installed, `python -m pytest` fails with
`No module named pytest`; install it with `python -m pip install pytest` and
run `python -m pytest` again.

本仓库用于 Orbi beta 端到端测试

最后更新于 2026-09-28
回归测试 2026-09-28
回归测试 v0.6.82
回归测试 v0.6.106
