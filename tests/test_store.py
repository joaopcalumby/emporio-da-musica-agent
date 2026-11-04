from datetime import date

import pytest

from emporio.store import Store
from tests.conftest import DATA_DIR


def ids(products: list[dict]) -> set[int]:
    return {product["id"] for product in products}


def test_categories_only_list_those_with_products(store):
    names = {category["name"] for category in store.list_categories()}
    assert names == {
        "Guitarras",
        "Baixos",
        "Baterias e Percussão",
        "Teclados e Pianos",
        "Violões",
        "Ukuleles",
    }


def test_acoustic_guitars_up_to_1000(store):
    result = store.search_products(category="violoes", max_price=1000)
    assert ids(result["products"]) == {81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 96, 107, 112}


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("guitarras elétricas", {131, 132, 133, 134, 145}),
        ("guitarra", {131, 132, 133, 134, 145}),
    ],
)
def test_category_matches_singular_and_qualified_names(store, category, expected):
    assert ids(store.search_products(category=category)["products"]) == expected


def test_singular_category_matches_plural(store):
    singular = ids(store.search_products(category="violão")["products"])
    assert singular and singular == ids(store.search_products(category="Violões")["products"])


def test_similar_instrument_does_not_match_another_category(store):
    assert store.search_products(category="violino")["products"] == []


def test_out_of_stock_product_is_listed_as_unavailable(store):
    result = store.search_products(category="Violões", max_price=1000)
    giannini = next(p for p in result["products"] if p["id"] == 96)
    assert giannini["availability"] == "out_of_stock"


def test_search_hides_coming_soon_and_discontinued_without_stock(store):
    found = ids(store.search_products()["products"])
    assert 130 not in found
    assert 113 not in found
    assert 136 in found


def test_category_without_products_is_reported(store):
    result = store.search_products(query="saxofone")
    assert result["products"] == []
    assert result["categories_without_products"] == ["Instrumentos de Sopro (Madeiras)"]


def test_takamine_gd20_price_stock_and_pix(store):
    product = store.find_product("Takamine GD20")
    assert product["id"] == 95
    assert product["price"] == 2199
    assert product["stock"] == 5
    assert product["promotion"] is None
    assert product["pix_price"] == 2089.05


def test_active_promotion_shows_original_price_and_no_pix_discount(store):
    product = store.find_product("Taylor 110e")
    assert product["price"] == 5999
    assert product["promotion"] == {
        "description": "Desconto Exclusivo",
        "discount_percent": 8,
        "price": 5519.08,
    }
    assert product["pix_price"] is None


def test_products_on_sale(store):
    assert ids(store.search_products(on_sale=True)["products"]) == {90, 94, 121, 127}


def test_acoustic_guitars_on_sale(store):
    assert ids(store.search_products(category="Violões", on_sale=True)["products"]) == {90, 94}


def test_inactive_promotion_is_ignored(store):
    assert store.find_product("Martin D-28")["promotion"] is None


@pytest.mark.parametrize(
    ("name", "availability"),
    [
        ("Kala KA-ABP-CTG", "coming_soon"),
        ("Ibanez Bass 2X", "last_units"),
        ("Shelby SN-7C", "discontinued"),
        ("Giannini GF-3D", "out_of_stock"),
        ("Yamaha C40", "available"),
    ],
)
def test_availability(store, name, availability):
    assert store.find_product(name)["availability"] == availability


def test_unknown_product(store):
    assert store.find_product("Stradivarius") is None


@pytest.mark.parametrize(
    ("amount", "installments", "allowed"),
    [
        (159.90, 3, True),
        (120.00, 3, False),
        (349.90, 4, True),
        (349.90, 6, False),
        (840.00, 7, True),
        (700.00, 10, False),
        (1200.00, 12, True),
        (5999.00, 13, False),
    ],
)
def test_can_split(store, amount, installments, allowed):
    assert store.can_split(amount, installments) is allowed


def test_max_installments(store):
    assert store.installments(349.90) == {"max_installments": 4, "installment_value": 87.48}


@pytest.mark.parametrize(
    ("city", "amount", "fee"),
    [
        ("Campo Grande", 599.90, 0.0),
        ("Campo Grande", 500.00, 0.0),
        ("Campo Grande", 499.99, 35.0),
        ("campo grande", 429.90, 35.0),
        ("Dourados", 599.90, None),
    ],
)
def test_shipping_fee(store, city, amount, fee):
    assert store.shipping(city, amount)["fee"] == fee


def test_order_with_matching_email(store):
    order = store.order_status(8, "anacarol.ferreira@coldmail.com")
    assert order["status"] == "shipped"
    assert order["tracking_code"] == "BRJL5544332BR"


def test_order_with_matching_phone(store):
    assert store.order_status(8, "67996547821")["id"] == 8


def test_order_with_wrong_contact_leaks_nothing(store):
    assert store.order_status(8, "someone@else.com") == {"error": "verification_failed"}


def test_unknown_order(store):
    assert store.order_status(99, "anacarol.ferreira@coldmail.com") == {"error": "order_not_found"}


def test_shared_email_requires_phone(store):
    assert store.order_status(10, "bruno.martins@jmail.com") == {"error": "phone_required"}
    assert store.order_status(10, "(67) 98543-2109")["id"] == 10


def test_order_total_is_the_recorded_one(store):
    assert store.order_status(20, "thiago.barbosa@jmail.com")["total"] == 1400


def test_return_window_open():
    store = Store.from_dir(DATA_DIR, today=date(2026, 2, 20))
    order = store.order_status(7, "leticia.rocha@jmail.com")
    assert order["return"] == {"eligible": True, "deadline": "2026-02-24"}


def test_return_window_closed(store):
    order = store.order_status(7, "leticia.rocha@jmail.com")
    assert order["return"] == {"eligible": False, "deadline": "2026-02-24"}

