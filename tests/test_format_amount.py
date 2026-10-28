from stripe_payments import format_amount


def test_format_amount_uses_two_decimals():
    assert format_amount(1999, "usd") == "19.99 USD"


def test_format_amount_adds_thousands_separators():
    # Issue #221: 1 234 567.89 must not be one run of digits.
    assert format_amount(123456789, "usd") == "1,234,567.89 USD"


def test_format_amount_uppercases_the_currency():
    assert format_amount(123456, "eur") == "1,234.56 EUR"


def test_format_amount_keeps_zero_decimal_currencies_integer():
    # Stripe's zero-decimal list: 500 is 500 JPY, not 5.00 JPY.
    assert format_amount(500, "jpy") == "500 JPY"
    assert format_amount(1234567, "krw") == "1,234,567 KRW"


def test_format_amount_treats_ugx_as_the_two_decimal_value_stripe_documents():
    # Stripe's "Special cases" (docs.stripe.com/currencies) says UGX amounts are
    # represented as a two-decimal value: to charge 5 UGX, pass 500.  A UGX
    # total must therefore not be printed as the raw integer.
    assert format_amount(500, "ugx") == "5.00 UGX"


def test_format_amount_formats_negative_amounts_without_losing_the_sign():
    assert format_amount(-50, "usd") == "-0.50 USD"
    assert format_amount(-123456, "usd") == "-1,234.56 USD"
