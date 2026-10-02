"""Order checkout.

The rules live in `src/shop/specs/checkout.md` - read it first.
The signatures and the constants are final: the tests rely on them.
"""

from shop.money import percent_of

PROMO_CODES = {"WELCOME10": 10, "SUMMER15": 15, "VIP35": 35}
SUPPORTED_CITIES = ("msk", "spb")
MAX_DISCOUNT_PERCENT = 30
VAT_PERCENT = 20
SHIPPING_KOPEKS = 49_000
FREE_DELIVERY_FROM_KOPEKS = 500_000
TIER_DISCOUNTS = ((10, 5), (25, 10), (50, 15))
REQUIRED_LINE_KEYS = ("sku", "qty", "unit_price_kopecks")


def _parse_int(text: str) -> int | None:
    """Parse `text` the way int() does, returning None instead of raising.

    try/except is banned by the project rules, so int() is only called on the
    exact shape it cannot fail on: optional sign plus decimal digits, with the
    surrounding whitespace int() skips anyway.
    """
    body = text.strip()
    digits = body[1:] if body[:1] in {"+", "-"} else body
    if not digits.isdecimal():
        return None
    return int(body)


def _check_line(position: int, item: dict[str, str], seen_skus: set[str]) -> str | None:
    """Apply spec rules 2-8 to one order line, tracking seen skus on the way."""
    for key in REQUIRED_LINE_KEYS:
        if key not in item:
            return f"line {position}: missing required key {key}"
    if not item["sku"]:
        return f"line {position}: sku must not be empty"
    if item["sku"] in seen_skus:
        return f"line {position}: sku {item['sku']} is duplicated"
    seen_skus.add(item["sku"])

    quantity = _parse_int(item["qty"])
    if quantity is None:
        return f"line {position}: qty is not an integer"
    if quantity <= 0:
        return f"line {position}: qty must be greater than zero"

    price = _parse_int(item["unit_price_kopecks"])
    if price is None:
        return f"line {position}: unit_price_kopecks is not an integer"
    if price < 0:
        return f"line {position}: unit_price_kopecks must not be negative"
    return None


def _tier_percent(units: int) -> int:
    """Return the percentage of the highest tier the unit count reaches."""
    best_threshold = -1
    percent = 0
    for threshold, tier_percent in TIER_DISCOUNTS:
        if units >= threshold and threshold > best_threshold:
            best_threshold = threshold
            percent = tier_percent
    return percent


def _discount_percent(units: int, promo_code: str) -> int:
    """Take the bigger of the tier and the promo percentage, then cap it.

    The two discounts never add up: spec step 4 picks one of them.
    """
    promo_percent = PROMO_CODES.get(promo_code, 0)
    return min(max(_tier_percent(units), promo_percent), MAX_DISCOUNT_PERCENT)


def validate_order(
    lines: list[dict[str, str]],
    promo_code: str = "",
    shipping_city: str = "",
) -> str | None:
    """Return a human readable reason why the order is invalid, or None if it is fine."""
    if not lines:
        return "the order has no lines"

    seen_skus: set[str] = set()
    for position, item in enumerate(lines, start=1):
        problem = _check_line(position, item, seen_skus)
        if problem is not None:
            return problem

    if promo_code and promo_code not in PROMO_CODES:
        return f"unknown promo code {promo_code}"
    if shipping_city and shipping_city not in SUPPORTED_CITIES:
        return f"unsupported shipping city {shipping_city}"
    return None


def calculate_order_total(
    lines: list[dict[str, str]],
    promo_code: str = "",
    shipping_city: str = "",
) -> int | None:
    """Return the order total in kopecks, or None if the order is invalid."""
    if validate_order(lines, promo_code, shipping_city) is not None:
        return None

    subtotal = 0
    units = 0
    for item in lines:
        # validate_order has already proved both fields parse as integers.
        quantity = int(item["qty"])
        units += quantity
        subtotal += quantity * int(item["unit_price_kopecks"])

    discount = percent_of(subtotal, _discount_percent(units, promo_code))
    discounted_subtotal = subtotal - discount

    # The free delivery threshold compares against the sum after the discount.
    delivery = 0
    if shipping_city and discounted_subtotal < FREE_DELIVERY_FROM_KOPEKS:
        delivery = SHIPPING_KOPEKS

    base = discounted_subtotal + delivery
    vat = percent_of(base, VAT_PERCENT)
    return base + vat
