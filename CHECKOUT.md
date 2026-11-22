# 结算页（Checkout）

结算页支付失败时，表单最上方会显示一条**深红色（暗红）**的错误条，条内文字为
`Payment failed: invalid card`，颜色为深红色（暗红，截图只提供观感，因此不写具体
十六进制色号）；在原型 `checkout.html` 中，这条错误条的 class 名为 `error-banner`
（`<div class="error-banner" role="alert">`，`role="alert"` 让读屏软件立即播报）。

## 退款订单

订单表 `orders.csv` 中 `refund` 列大于 0 的订单发生过退款，只有这一笔：

- `1002`：金额 15.50，退款 15.50（全额退款）
