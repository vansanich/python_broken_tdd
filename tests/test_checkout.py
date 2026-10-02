"""Order checkout, part 2.

How to work through this file:

1. The single red test below is done for you - it shows what RED looks like.
2. Run `./scripts/check-part2.sh` and read the failure.
3. Write one assertion per rule from `src/shop/specs/checkout.md` into the empty
   tests: a failing test first, then the code that makes it pass.
4. Never edit a finished assertion, never `skip`, never weaken a test.

Run one test at a time while you work:

    uv run pytest tests/test_checkout.py -k tier -x
"""

from shop.checkout import calculate_order_total, validate_order


def line(sku: str = "SKU-1", qty: str = "1", unit_price_kopecks: str = "10000") -> dict[str, str]:
    """Build one order line the way the warehouse export delivers it."""
    return {"sku": sku, "qty": qty, "unit_price_kopecks": unit_price_kopecks}


def test_smoke_single_line_without_delivery() -> None:
    """One line, no promo code, no delivery. Works out to 100.00 rub + 20% VAT."""
    assert validate_order([line()]) is None
    assert calculate_order_total([line()]) == 12_000


def test_empty_order_is_rejected() -> None:
    """Spec 3, rule 1: an order without lines cannot be processed."""
    reason = validate_order([])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([]) is None


def test_empty_sku_is_rejected() -> None:
    """Spec 3, rule 2: a blank article code is not allowed."""
    reason = validate_order([line(sku="")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(sku="")]) is None


def test_missing_line_key_is_rejected() -> None:
    """Spec 3, rule 3: every required key must be present."""
    broken = line()
    del broken["qty"]
    reason = validate_order([broken])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([broken]) is None


def test_non_numeric_quantity_is_rejected() -> None:
    """Spec 3, rule 4: `qty` must be a whole number."""
    reason = validate_order([line(qty="two")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(qty="two")]) is None


def test_zero_quantity_is_rejected() -> None:
    """Spec 3, rule 5: `qty` must be greater than zero."""
    reason = validate_order([line(qty="0")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(qty="0")]) is None


def test_non_numeric_price_is_rejected() -> None:
    """Spec 3, rule 6: `unit_price_kopecks` must be a whole number."""
    reason = validate_order([line(unit_price_kopecks="10.5")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(unit_price_kopecks="10.5")]) is None


def test_negative_price_is_rejected() -> None:
    """Spec 3, rule 7: a price may not be negative."""
    reason = validate_order([line(unit_price_kopecks="-100")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(unit_price_kopecks="-100")]) is None


def test_duplicate_sku_is_rejected() -> None:
    """Spec 3, rule 8: the same article may appear only once."""
    reason = validate_order([line(sku="SAME"), line(sku="SAME")])
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line(sku="SAME"), line(sku="SAME")]) is None


def test_unknown_promo_code_is_rejected() -> None:
    """Spec 3, rule 9: only codes from PROMO_CODES exist."""
    reason = validate_order([line()], promo_code="HOLIDAY20")
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line()], promo_code="HOLIDAY20") is None


def test_unsupported_city_is_rejected() -> None:
    """Spec 3, rule 10: only cities from SUPPORTED_CITIES are served."""
    reason = validate_order([line()], shipping_city="kazan")
    assert reason is not None
    assert reason.strip()
    assert calculate_order_total([line()], shipping_city="kazan") is None


def test_valid_order_passes_validation() -> None:
    """Spec 3: a good order gets None back instead of a reason."""
    assert validate_order([line()], "WELCOME10", "msk") is None
    # 10 000 - 10% promo = 9 000, +49 000 delivery, then 20% VAT.
    assert calculate_order_total([line()], "WELCOME10", "msk") == 69_600


def test_no_discount_below_first_tier() -> None:
    """Spec 4, steps 1-2: 9 units are below every threshold."""
    assert calculate_order_total([line(qty="9", unit_price_kopecks="1990")]) == 21_492


def test_tier_discount_at_first_threshold() -> None:
    """Spec 4, steps 2-5: 10 units give 5%. Compare with example 2."""
    assert calculate_order_total([line(qty="10", unit_price_kopecks="1990")]) == 22_686


def test_tier_discount_at_highest_threshold() -> None:
    """Spec 4, steps 2-5: 50 units give 15%, not 5% + 10%."""
    # 25 units reach the second tier only: 10%.
    assert calculate_order_total([line(qty="25", unit_price_kopecks="1990")]) == 53_730
    # 50 units reach the top tier: 15%.
    assert calculate_order_total([line(qty="50", unit_price_kopecks="1990")]) == 101_490


def test_promo_code_beats_tier_discount() -> None:
    """Spec 4, steps 3-4: the bigger percentage wins, the two do not add up."""
    # 10 units give a 5% tier discount, WELCOME10 gives 10%. 15% would be wrong.
    total = calculate_order_total([line(qty="10", unit_price_kopecks="1990")], "WELCOME10")
    assert total == 21_492


def test_discount_is_capped_at_thirty_percent() -> None:
    """Spec 4, step 5: VIP35 gives 35%, but the cap is 30%. Compare with example 4."""
    total = calculate_order_total([line(qty="100", unit_price_kopecks="10000")], "VIP35", "spb")
    assert total == 840_000


def test_delivery_is_charged_for_small_order() -> None:
    """Spec 4, steps 7-10: a city adds SHIPPING_KOPEKS and VAT is charged on it."""
    order = [line(qty="50", unit_price_kopecks="1990")]
    with_city = calculate_order_total(order, "WELCOME10", "msk")
    without_city = calculate_order_total(order, "WELCOME10")
    assert with_city is not None
    assert without_city is not None
    # Example 3 of the spec: 49 000 delivery plus 20% VAT on top of it.
    assert with_city - without_city == 58_800
    assert with_city == 160_290


def test_free_delivery_uses_discounted_subtotal() -> None:
    """Spec 4, step 7: the threshold is checked against the sum after the discount."""
    # 700 000 falls below the threshold after the 30% cap, so delivery is paid.
    discounted = calculate_order_total([line(qty="100", unit_price_kopecks="7000")], "VIP35", "msk")
    assert discounted == 646_800
    # Exactly on the threshold delivery is already free.
    assert calculate_order_total([line(qty="1", unit_price_kopecks="500000")], "", "msk") == 600_000
    # One kopeck short: delivery is charged.
    assert calculate_order_total([line(qty="1", unit_price_kopecks="499999")], "", "msk") == 658_799


def test_vat_is_charged_on_the_discounted_sum() -> None:
    """Spec 4, steps 8-10: base = discounted subtotal + delivery."""
    # 19 900 - 15% = 16 915, so VAT must be 3 383, not 3 980 on the raw subtotal.
    total = calculate_order_total([line(qty="10", unit_price_kopecks="1990")], "SUMMER15")
    assert total == 20_298
