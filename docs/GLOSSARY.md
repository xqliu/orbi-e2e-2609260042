# Glossary

本页解释 README 里出现的三个词，每个词都能在 [README](../README.md) 中找到实例。

## e2e

端到端（end-to-end）测试：从真实入口一路验证到用户可见的结果，而不是只测单个函数。
README 说的「这是 Orbi beta 的端到端（e2e）测试仓库」，指本仓库用它自己的命令行入口
（`python -m pytest` 与 `python -m stripe_payments ...`）检验交付物是否真的可用。

## pytest

本仓库使用的测试运行器。执行 `python -m pytest` 时，它会收集 `tests/` 下以 `test_`
开头的函数逐个运行，并在最后打印汇总，例如 `181 passed in 63.93s`；汇总里没有
`failed` 就表示全部通过。

## PaymentIntent

Stripe 对「一笔付款意图」的记录，id 形如 `pi_...`。README 的 `export` 一节会把账户的
PaymentIntents 写成文件，live 验证成功时日志打印的
`payment_intent id=pi_... status=succeeded` 就是它的 id 与状态。
