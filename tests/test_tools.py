import inspect
import json

import pytest
from agno.tools.function import Function

from emporio.agent import build_tools
from emporio.policies import PolicyIndex, load_sections
from tests.conftest import DATA_DIR


@pytest.fixture(scope="module")
def tools(store):
    policies = PolicyIndex.build(load_sections(DATA_DIR / "store_policies.pdf"))
    return {tool.__name__: tool for tool in build_tools(store, policies)}


def call(tools, tool, **kwargs):
    return json.loads(tools[tool](**kwargs))


def test_exposed_tools(tools):
    assert set(tools) == {
        "list_categories",
        "search_products",
        "get_product",
        "simulate_installments",
        "shipping_quote",
        "order_status",
        "search_policies",
    }


def test_optional_parameters_accept_null(tools):
    for tool in tools.values():
        properties = Function.from_callable(tool).parameters["properties"]
        for name, parameter in inspect.signature(tool).parameters.items():
            if parameter.default is not inspect.Parameter.empty:
                assert {"type": "null"} in properties[name].get("anyOf", []), f"{tool.__name__}.{name}"


def test_search_results_are_compact(tools):
    products = call(tools, "search_products", category="Violões", max_price=1000)["products"]
    assert len(products) == 13
    assert all("description" not in p and "specs" not in p for p in products)
    assert {"name", "price", "promotion", "pix_price", "availability"} <= set(products[0])


def test_search_on_sale(tools):
    products = call(tools, "search_products", on_sale=True)["products"]
    assert {p["id"] for p in products} == {90, 94, 121, 127}


def test_product_details_include_specs(tools):
    assert "specs" in call(tools, "get_product", name="Takamine GD20")


def test_unknown_product(tools):
    assert call(tools, "get_product", name="Stradivarius") == {"error": "product_not_found"}


def test_installments_for_a_given_count(tools):
    assert call(tools, "simulate_installments", amount=349.90, installments=6) == {
        "allowed": False,
        "max_installments": 4,
        "installment_value": 87.48,
    }


def test_order_status_requires_contact(tools):
    assert call(tools, "order_status", order_id=8, email_or_phone="x@y.com") == {"error": "verification_failed"}


def test_policy_search_returns_sections(tools):
    sections = call(tools, "search_policies", question="Posso trocar a boquilha do saxofone?")
    assert any(s["section"] == "4.4" and "Boquilhas" in s["text"] for s in sections)
