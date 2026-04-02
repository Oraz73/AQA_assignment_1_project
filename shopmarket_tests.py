# ============================================================
# ShopMarket - Automated Tests (Assignment 2)
# Запуск: pytest shopmarket_tests.py -v --html=report.html --self-contained-html
# ============================================================

import requests
import pytest

BASE = "http://localhost:8000"

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def login(email, password):
    resp = requests.post(f"{BASE}/api/auth/login/", json={"email": email, "password": password})
    return resp.json().get("access")

def headers(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def buyer_token():
    token = login("buyer1@test.com", "Test123!")
    assert token, "Could not login as buyer — check seed data"
    return token

@pytest.fixture(scope="session")
def admin_token():
    token = login("admin@marketplace.com", "Admin123!")
    assert token, "Could not login as admin"
    return token


# ─────────────────────────────────────────────
# TC-A01 to TC-A06: AUTHENTICATION & JWT (P1)
# ─────────────────────────────────────────────

def test_TC_A01_valid_login_returns_tokens():
    """Valid login returns access and refresh tokens"""
    resp = requests.post(f"{BASE}/api/auth/login/", json={
        "email": "buyer1@test.com", "password": "Test123!"
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.json()
    assert "access" in body, "No access token in response"
    assert "refresh" in body, "No refresh token in response"


def test_TC_A02_wrong_password_returns_401():
    """Wrong password must return 401"""
    resp = requests.post(f"{BASE}/api/auth/login/", json={
        "email": "buyer1@test.com", "password": "WrongPassword!"
    })
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_TC_A03_no_token_returns_401():
    """Accessing cart without token must return 401"""
    resp = requests.get(f"{BASE}/api/cart/")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


def test_TC_A04_token_refresh_works():
    """Refresh token must return a new access token"""
    login_resp = requests.post(f"{BASE}/api/auth/login/", json={
        "email": "buyer1@test.com", "password": "Test123!"
    })
    refresh = login_resp.json()["refresh"]
    resp = requests.post(f"{BASE}/api/auth/token/refresh/", json={"refresh": refresh})
    assert resp.status_code == 200
    assert "access" in resp.json()


def test_TC_A05_logout_blacklists_token():
    """After logout, refresh token must be rejected"""
    login_resp = requests.post(f"{BASE}/api/auth/login/", json={
        "email": "buyer1@test.com", "password": "Test123!"
    })
    tokens = login_resp.json()
    access = tokens["access"]
    refresh = tokens["refresh"]

    logout = requests.post(f"{BASE}/api/auth/logout/",
        json={"refresh": refresh},
        headers={"Authorization": f"Bearer {access}"}
    )
    assert logout.status_code in [200, 205], f"Logout failed: {logout.status_code}"

    retry = requests.post(f"{BASE}/api/auth/token/refresh/", json={"refresh": refresh})
    assert retry.status_code == 401, "Blacklisted token was accepted — SECURITY BUG!"


def test_TC_A06_me_endpoint_returns_user(buyer_token):
    """/api/auth/me/ returns current user info"""
    resp = requests.get(f"{BASE}/api/auth/me/", headers=headers(buyer_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data


# ─────────────────────────────────────────────
# TC-C01 to TC-C07: SHOPPING CART (P1)
# ─────────────────────────────────────────────

def test_TC_C01_get_cart_returns_200(buyer_token):
    """Authenticated user can get their cart"""
    resp = requests.get(f"{BASE}/api/cart/", headers=headers(buyer_token))
    assert resp.status_code == 200


def test_TC_C02_add_item_to_cart(buyer_token):
    """Can add a product to cart"""
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    resp = requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 1},
        headers=headers(buyer_token)
    )
    assert resp.status_code == 201, f"Add to cart failed: {resp.status_code} {resp.text}"


def test_TC_C03_zero_quantity_rejected(buyer_token):
    """Quantity 0 must be rejected"""
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    resp = requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 0},
        headers=headers(buyer_token)
    )
    assert resp.status_code in [400, 422], f"Expected 400/422 for qty=0, got {resp.status_code}"


def test_TC_C04_negative_quantity_rejected(buyer_token):
    """Negative quantity must be rejected"""
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    resp = requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": -3},
        headers=headers(buyer_token)
    )
    assert resp.status_code in [400, 422], f"Expected 400/422 for qty=-3, got {resp.status_code}"


def test_TC_C05_apply_valid_coupon(buyer_token):
    """Valid coupon SAVE10 must apply successfully"""
    resp = requests.post(f"{BASE}/api/cart/apply-coupon/",
        json={"code": "SAVE10"},
        headers=headers(buyer_token)
    )
    assert resp.status_code == 200, f"Coupon failed: {resp.status_code} {resp.text}"


def test_TC_C06_invalid_coupon_rejected(buyer_token):
    """Fake coupon code must return 400"""
    resp = requests.post(f"{BASE}/api/cart/apply-coupon/",
        json={"code": "FAKECODE999"},
        headers=headers(buyer_token)
    )
    assert resp.status_code == 400, f"Expected 400 for fake coupon, got {resp.status_code}"


def test_TC_C07_clear_cart(buyer_token):
    """Clear cart must remove all items"""
    resp = requests.delete(f"{BASE}/api/cart/clear/", headers=headers(buyer_token))
    assert resp.status_code in [200, 204], f"Clear cart failed: {resp.status_code}"
    cart = requests.get(f"{BASE}/api/cart/", headers=headers(buyer_token)).json()
    assert len(cart.get("items", [])) == 0, "Cart not empty after clear"


# ─────────────────────────────────────────────
# TC-O01 to TC-O05: ORDER CREATION (P1)
# ─────────────────────────────────────────────

def setup_cart(token):
    """Clear cart and add one item"""
    requests.delete(f"{BASE}/api/cart/clear/", headers=headers(token))
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 1},
        headers=headers(token)
    )
    return product_id


def test_TC_O01_create_order(buyer_token):
    """Can create order from cart"""
    setup_cart(buyer_token)
    resp = requests.post(f"{BASE}/api/orders/",
        json={"shipping_address": "123 Test Street, Almaty"},
        headers=headers(buyer_token)
    )
    assert resp.status_code == 201, f"Order creation failed: {resp.status_code} {resp.text}"
    order = resp.json()
    assert "id" in order
    assert order.get("status") == "pending"


def test_TC_O02_order_total_correct(buyer_token):
    """Order total must match cart total"""
    setup_cart(buyer_token)
    cart = requests.get(f"{BASE}/api/cart/", headers=headers(buyer_token)).json()
    cart_total = float(cart.get("total", cart.get("subtotal", 0)))

    order_resp = requests.post(f"{BASE}/api/orders/",
        json={"shipping_address": "123 Test Street"},
        headers=headers(buyer_token)
    )
    assert order_resp.status_code == 201
    order_total = float(order_resp.json().get("total_price", 0))
    assert abs(cart_total - order_total) < 0.01, \
        f"Cart total {cart_total} != order total {order_total}"


def test_TC_O03_stock_decreases_after_order(buyer_token):
    """Stock must decrease by 1 after ordering"""
    products = requests.get(f"{BASE}/api/products/").json()
    product = products["results"][0]
    product_id = product["id"]
    stock_before = product["stock"]

    requests.delete(f"{BASE}/api/cart/clear/", headers=headers(buyer_token))
    requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 1},
        headers=headers(buyer_token)
    )
    requests.post(f"{BASE}/api/orders/",
        json={"shipping_address": "123 Test Street"},
        headers=headers(buyer_token)
    )
    product_after = requests.get(f"{BASE}/api/products/{product_id}/").json()
    assert product_after["stock"] == stock_before - 1, \
        f"Stock should be {stock_before - 1}, got {product_after['stock']}"


def test_TC_O04_cannot_order_more_than_stock(buyer_token):
    """Cannot add more items than available stock"""
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    requests.delete(f"{BASE}/api/cart/clear/", headers=headers(buyer_token))
    resp = requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 99999},
        headers=headers(buyer_token)
    )
    assert resp.status_code in [400, 422], \
        f"Expected 400/422 for oversell, got {resp.status_code}"


def test_TC_O05_cancel_pending_order(buyer_token):
    """Can cancel a pending order"""
    setup_cart(buyer_token)
    order = requests.post(f"{BASE}/api/orders/",
        json={"shipping_address": "123 Test Street"},
        headers=headers(buyer_token)
    ).json()
    order_id = order["id"]
    cancel = requests.post(f"{BASE}/api/orders/{order_id}/cancel/",
        headers=headers(buyer_token)
    )
    assert cancel.status_code in [200, 204], f"Cancel failed: {cancel.status_code}"


# ─────────────────────────────────────────────
# TC-P01 to TC-P03: PRODUCT CATALOG (P2)
# ─────────────────────────────────────────────

def test_TC_P01_product_list_returns_products():
    """Product list must return seeded products"""
    resp = requests.get(f"{BASE}/api/products/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1, "No products found"
    assert len(body["results"]) > 0


def test_TC_P02_product_detail_has_required_fields():
    """Product detail must contain key fields"""
    products = requests.get(f"{BASE}/api/products/").json()
    product_id = products["results"][0]["id"]
    resp = requests.get(f"{BASE}/api/products/{product_id}/")
    assert resp.status_code == 200
    data = resp.json()
    for field in ["id", "title", "price", "stock"]:
        assert field in data, f"Missing field: {field}"


def test_TC_P03_search_returns_results():
    """Search must filter products"""
    resp = requests.get(f"{BASE}/api/products/", params={"search": "iPhone"})
    assert resp.status_code == 200
    assert resp.json()["count"] >= 0  # search works without error


# ─────────────────────────────────────────────
# TC-CP01 to TC-CP02: COUPONS (P2)
# ─────────────────────────────────────────────

def test_TC_CP01_save10_applies_discount(buyer_token):
    """SAVE10 coupon must apply 10% discount"""
    requests.delete(f"{BASE}/api/cart/clear/", headers=headers(buyer_token))
    products = requests.get(f"{BASE}/api/products/").json()
    product = products["results"][0]
    product_id = product["id"]
    price = float(product["price"])

    requests.post(f"{BASE}/api/cart/items/",
        json={"product_id": product_id, "quantity": 1},
        headers=headers(buyer_token)
    )
    apply = requests.post(f"{BASE}/api/cart/apply-coupon/",
        json={"code": "SAVE10"},
        headers=headers(buyer_token)
    )
    assert apply.status_code == 200

    cart = requests.get(f"{BASE}/api/cart/", headers=headers(buyer_token)).json()
    actual_total = float(cart.get("total", cart.get("subtotal", 0)))
    expected_total = round(price * 0.9, 2)
    assert abs(actual_total - expected_total) < 0.10, \
        f"Expected ~{expected_total} (10% off {price}), got {actual_total}"


def test_TC_CP02_invalid_coupon_returns_400(buyer_token):
    """Invalid coupon must return 400"""
    resp = requests.post(f"{BASE}/api/cart/apply-coupon/",
        json={"code": "NOTREAL"},
        headers=headers(buyer_token)
    )
    assert resp.status_code == 400
