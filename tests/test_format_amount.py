from stripe_payments import format_amount


def test_format_amount_uses_two_decimals():
    assert format_amount(1999, "usd") == "19.99 USD"
