# Security

如果你在本仓库（含 `stripe_payments.py` 及 CI 配置）发现安全问题，请不要公开提 Issue，
也不要把细节写在 pull request 里。

请通过邮件私下上报：support@orbi.build

邮件里请写清这三点，方便维护者复现：

- 受影响的文件或命令（例如 `python -m stripe_payments export`）
- 复现步骤，以及你实际看到的输出
- 可能的影响范围（例如密钥泄露、误扣款）

维护者会通过同一个邮箱回复你，确认问题与后续处理方式。上报的问题修复并公开之后，
再在 Issue 里讨论一般性问题即可。
