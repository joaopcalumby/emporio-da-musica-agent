import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PIX_DISCOUNT = Decimal("0.05")
RETURN_WINDOW_DAYS = 7
MAX_INSTALLMENTS = 12
FREE_SHIPPING_FROM = Decimal("500")
LOCAL_SHIPPING_FEE = 35.0
LOCAL_CITY = "campo grande"
PLURAL_ENDINGS = (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"), ("s", ""))
GENERIC_WORDS = {"instrumento"}
SEARCHABLE = {"available", "out_of_stock", "last_units"}
OTHER_CITY_OPTIONS = [
    {"carrier": "PAC (Correios)", "delivery": "5 a 12 dias úteis"},
    {"carrier": "SEDEX (Correios)", "delivery": "2 a 5 dias úteis"},
    {"carrier": "Jadlog (.package)", "delivery": "3 a 8 dias úteis"},
]


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def minimum_installment(installments: int) -> Decimal:
    if installments <= 3:
        return Decimal("50")
    if installments <= 6:
        return Decimal("80")
    return Decimal("100")


def singular(word: str) -> str:
    for plural, single in PLURAL_ENDINGS:
        if word.endswith(plural):
            return word[: -len(plural)] + single
    return word


def category_words(text: str) -> set[str]:
    return {singular(w) for w in re.findall(r"\w+", normalize(text)) if len(w) > 2} - GENERIC_WORDS


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


@dataclass
class Store:
    products: list[dict]
    categories: dict[str, dict]
    customers: dict[str, dict]
    orders: dict[str, dict]
    order_items: list[dict]
    active_promotions: dict[str, dict]
    today: date

    @classmethod
    def from_dir(cls, data_dir: Path, today: date) -> "Store":
        promotions = read_csv(data_dir / "promotions.csv")
        return cls(
            products=read_csv(data_dir / "products.csv"),
            categories={c["category_id"]: c for c in read_csv(data_dir / "categories.csv")},
            customers={c["customer_id"]: c for c in read_csv(data_dir / "customers.csv")},
            orders={o["order_id"]: o for o in read_csv(data_dir / "orders.csv")},
            order_items=read_csv(data_dir / "order_items.csv"),
            active_promotions={p["product_id"]: p for p in promotions if p["is_active"] == "1"},
            today=today,
        )

    def list_categories(self) -> list[dict]:
        counts = self._product_counts()
        return [
            {"name": c["name"], "description": c["description"], "products": counts[cid]}
            for cid, c in self.categories.items()
            if counts.get(cid)
        ]

    def search_products(
        self,
        category: str | None = None,
        max_price: float | None = None,
        query: str | None = None,
        on_sale: bool = False,
    ) -> dict:
        matching_categories = self._matching_category_ids(category, query)
        terms = normalize(query).split() if query else []
        products = [
            view
            for product in self.products
            if (view := self._view(product))["availability"] in SEARCHABLE
            and (category is None or product["category_id"] in matching_categories)
            and (max_price is None or view["final_price"] <= max_price)
            and all(term in self._searchable_text(product) for term in terms)
            and (not on_sale or view["promotion"])
        ]
        counts = self._product_counts()
        empty = [
            self.categories[cid]["name"]
            for cid in matching_categories
            if (category or query) and not counts.get(cid)
        ]
        return {"products": products, "categories_without_products": empty}

    def find_product(self, name: str) -> dict | None:
        terms = normalize(name).split()
        matches = [p for p in self.products if all(t in normalize(p["name"]) for t in terms)]
        if not matches:
            return None
        return self._view(min(matches, key=lambda p: len(p["name"])))

    def can_split(self, amount: float, installments: int) -> bool:
        if not 1 <= installments <= MAX_INSTALLMENTS:
            return False
        if installments == 1:
            return True
        return Decimal(str(amount)) / installments >= minimum_installment(installments)

    def installments(self, amount: float) -> dict:
        best = max(n for n in range(1, MAX_INSTALLMENTS + 1) if self.can_split(amount, n))
        return {
            "max_installments": best,
            "installment_value": money(Decimal(str(amount)) / best),
        }

    def shipping(self, city: str, amount: float | None) -> dict:
        if normalize(city) != LOCAL_CITY:
            return {"fee": None, "quote": "calculado pelo CEP de destino", "options": OTHER_CITY_OPTIONS}
        local = {"carrier": "motoboy próprio", "delivery": "1 a 3 dias úteis"}
        if amount is None:
            return {"fee": None, "free_from": money(FREE_SHIPPING_FROM), "fee_below": LOCAL_SHIPPING_FEE, **local}
        fee = 0.0 if Decimal(str(amount)) >= FREE_SHIPPING_FROM else LOCAL_SHIPPING_FEE
        return {"fee": fee, **local}

    def order_status(self, order_id: int, contact: str) -> dict:
        order = self.orders.get(str(order_id))
        if order is None:
            return {"error": "order_not_found"}
        customer = self.customers[order["customer_id"]]
        check = self._verify(customer, contact)
        if check:
            return {"error": check}
        return self._order_view(order, customer)

    def _verify(self, customer: dict, contact: str) -> str | None:
        if "@" in contact:
            email = normalize(contact)
            if email != normalize(customer["email"]):
                return "verification_failed"
            owners = [c for c in self.customers.values() if normalize(c["email"]) == email]
            return "phone_required" if len(owners) > 1 else None
        given = digits(contact)
        if len(given) < 10 or not digits(customer["phone"]).endswith(given[-11:]):
            return "verification_failed"
        return None

    def _order_view(self, order: dict, customer: dict) -> dict:
        estimated = date.fromisoformat(order["estimated_delivery"]) if order["estimated_delivery"] else None
        view = {
            "id": int(order["order_id"]),
            "customer_first_name": customer["name"].split()[0],
            "purchase_date": order["order_date"],
            "status": order["status"],
            "total": float(order["total_brl"]),
            "payment_method": order["payment_method"],
            "tracking_code": order["tracking_code"] or None,
            "estimated_delivery": order["estimated_delivery"] or None,
            "notes": order["notes"] or None,
            "items": self._items(order["order_id"]),
            "return": None,
        }
        if order["status"] == "delivered" and estimated:
            deadline = estimated + timedelta(days=RETURN_WINDOW_DAYS)
            view["return"] = {"eligible": self.today <= deadline, "deadline": deadline.isoformat()}
        if order["status"] == "shipped" and estimated:
            view["delivery_overdue"] = self.today > estimated
        return view

    def _items(self, order_id: str) -> list[dict]:
        names = {p["product_id"]: p["name"] for p in self.products}
        return [
            {"name": names.get(i["product_id"], f"produto {i['product_id']}"), "quantity": int(i["quantity"])}
            for i in self.order_items
            if i["order_id"] == order_id
        ]

    def _view(self, product: dict) -> dict:
        price = Decimal(product["price_brl"])
        promotion = self.active_promotions.get(product["product_id"])
        promo = None
        if promotion:
            discount = int(promotion["discount_percent"])
            promo = {
                "description": promotion["description"],
                "discount_percent": discount,
                "price": money(price * (100 - discount) / 100),
            }
        return {
            "id": int(product["product_id"]),
            "name": product["name"],
            "category": self.categories[product["category_id"]]["name"],
            "description": product["description"],
            "specs": product["specs"],
            "price": money(price),
            "promotion": promo,
            "pix_price": None if promo else money(price * (1 - PIX_DISCOUNT)),
            "final_price": promo["price"] if promo else money(price),
            "stock": int(product["stock_quantity"] or 0),
            "availability": self._availability(product),
        }

    @staticmethod
    def _availability(product: dict) -> str:
        in_stock = int(product["stock_quantity"] or 0) > 0
        match product["status"]:
            case "coming_soon":
                return "coming_soon"
            case "discontinued":
                return "last_units" if in_stock else "discontinued"
            case _:
                return "available" if in_stock else "out_of_stock"

    def _product_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for product in self.products:
            if self._availability(product) in SEARCHABLE:
                counts[product["category_id"]] = counts.get(product["category_id"], 0) + 1
        return counts

    def _matching_category_ids(self, category: str | None, query: str | None) -> list[str]:
        if category:
            wanted = category_words(category)
            return [cid for cid, c in self.categories.items() if wanted & category_words(c["name"])]
        if query:
            terms = normalize(query).split()
            return [
                cid
                for cid, c in self.categories.items()
                if any(t in normalize(f"{c['name']} {c['description']}") for t in terms)
            ]
        return list(self.categories)

    def _searchable_text(self, product: dict) -> str:
        category = self.categories[product["category_id"]]["name"]
        return normalize(f"{product['name']} {product['description']} {category}")
