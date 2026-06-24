EXPECTED_BUSINESS_ROUTES = {
    ("GET", "/"),
    ("GET", "/login"), ("POST", "/login"), ("GET", "/logout"),
    ("GET", "/dashboard"), ("GET", "/orders"),
    ("GET", "/api/suggest"), ("GET", "/api/recent-price"),
    ("POST", "/api/voice-order-query-draft"), ("POST", "/api/voice-order-draft"),
    ("GET", "/orders/new"), ("POST", "/orders"),
    ("GET", "/orders/{order_id}"),
    ("GET", "/orders/{order_id}/edit"), ("POST", "/orders/{order_id}/edit"),
    ("POST", "/orders/{order_id}/print"), ("POST", "/orders/batch-print"),
    ("GET", "/print-settings"), ("POST", "/print-settings/delivery-config"),
    ("POST", "/orders/{order_id}/paid"), ("POST", "/orders/{order_id}/unpaid"),
    ("POST", "/orders/{order_id}/payment"), ("POST", "/orders/{order_id}/delivered"),
    ("POST", "/orders/{order_id}/delete"), ("POST", "/orders/{order_id}/undo"),
    ("GET", "/robots.txt"), ("GET", "/showcase"),
    ("GET", "/showcase/manage"),
    ("GET", "/showcase/manage/new"), ("POST", "/showcase/manage/new"),
    ("POST", "/showcase/manage/delete"),
    ("POST", "/showcase/quotation/image"), ("POST", "/showcase/quotation/excel"),
    ("GET", "/users"), ("GET", "/users/new"), ("POST", "/users/new"),
    ("GET", "/users/{user_id}/edit"), ("POST", "/users/{user_id}/edit"),
    ("POST", "/users/{user_id}/delete"),
}


def test_business_route_contract():
    from app.main import app

    actual = set()
    for route in app.routes:
        if not getattr(route, "methods", None):
            continue
        if route.path in {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}:
            continue
        for method in route.methods:
            if method != "HEAD":
                actual.add((method, route.path))
    assert actual == EXPECTED_BUSINESS_ROUTES
