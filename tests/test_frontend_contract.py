import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
STATIC = ROOT / "app/static"


def test_all_templates_compile_and_share_layouts():
    environment = Environment(loader=FileSystemLoader(TEMPLATES))
    files = sorted(path.relative_to(TEMPLATES).as_posix() for path in TEMPLATES.rglob("*.html"))
    for filename in files:
        environment.get_template(filename)
    page_templates = [path for path in TEMPLATES.glob("*.html") if not path.name.startswith("_")]
    standalone = [path.name for path in page_templates if "<!DOCTYPE html>" in path.read_text(encoding="utf-8")]
    assert standalone == ["base.html"]


def test_static_references_and_css_imports_exist():
    referenced = set()
    for path in TEMPLATES.rglob("*.html"):
        referenced.update(re.findall(r'["\'](/static/[^"\'?]+)', path.read_text(encoding="utf-8")))
    for reference in referenced:
        assert (ROOT / "app" / reference.lstrip("/")).is_file(), reference

    css_entry = (STATIC / "css/app.css").read_text(encoding="utf-8")
    imports = re.findall(r'url\("(/static/[^"?]+)', css_entry)
    assert imports
    for reference in imports:
        assert (ROOT / "app" / reference.lstrip("/")).is_file(), reference


def test_templates_do_not_contain_inline_scripts_or_handlers():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.rglob("*.html"))
    assert not re.search(r"<script(?:\s[^>]*)?>\s*(?!</script>)", combined)
    assert "onclick=" not in combined
    assert "onsubmit=" not in combined


def test_responsive_shell_and_accessible_mobile_controls_are_stable():
    admin_layout = (TEMPLATES / "layouts/admin.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "components/nav.html").read_text(encoding="utf-8")
    bottom_nav = (TEMPLATES / "components/bottom_nav.html").read_text(encoding="utf-8")
    orders = (TEMPLATES / "orders.html").read_text(encoding="utf-8")
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    mobile_ui = (STATIC / "mobile_ui.js").read_text(encoding="utf-8")

    assert 'id="main-content"' in admin_layout
    assert "data-mobile-menu" in admin_layout
    assert 'id="appSidebar"' in nav
    assert nav.count('aria-current="page"') >= 7
    assert bottom_nav.count("<a ") == 4
    assert "data-mobile-card-toggle" in orders
    assert "data-mobile-card-toggle" in dashboard
    assert 'card.setAttribute("role", "button")' not in mobile_ui


def test_ui_refresh_and_service_worker_versions_match():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    css_entry = (STATIC / "css/app.css").read_text(encoding="utf-8")
    service_worker = (STATIC / "sw.js").read_text(encoding="utf-8")

    assert "/static/css/ui-refresh.css" in css_entry
    assert "/static/css/ui-refresh.css" in service_worker
    assert "app.css?v=20260621-4" in base
    assert "app.css?v=20260621-4" in service_worker
    assert "orders.js?v=20260621-2" in service_worker
    assert 'CACHE_NAME = "order-app-v8"' in service_worker


def test_mobile_order_workflow_hides_printing_and_keeps_desktop_printing():
    orders = (TEMPLATES / "orders.html").read_text(encoding="utf-8")
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    detail = (TEMPLATES / "order_detail.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "components/nav.html").read_text(encoding="utf-8")
    ui_css = (STATIC / "css/ui-refresh.css").read_text(encoding="utf-8")

    assert "data-open-mobile-payment" in orders
    assert 'id="mobilePaymentModal"' in orders
    assert 'data-payment-action="/orders/{{ order.id }}/payment"' in orders
    assert "mobile-print-hidden" in orders
    assert "mobile-print-hidden" in dashboard
    assert "mobile-print-hidden" in detail
    assert "mobile-print-hidden" in nav
    assert ".mobile-print-hidden" in ui_css
    assert '@media (max-width: 768px)' in ui_css
    assert 'action="/orders/batch-print"' in orders
    assert '/orders/{{ order.id }}/print' in detail


def test_delivery_print_uses_one_full_a4_sheet_per_order():
    template = (TEMPLATES / "delivery_print_a4.html").read_text(encoding="utf-8")
    document_css = (STATIC / "css/runtime/print-document.css").read_text(encoding="utf-8")
    print_css = (STATIC / "css/runtime/print-responsive.css").read_text(encoding="utf-8")

    assert "for copy_label in print_config.copies" not in template
    assert template.count('<article class="delivery-copy">') == 1
    assert "range(7)" in template
    assert "width: 210mm" in document_css
    assert "height: 297mm" in document_css
    assert "font-size: 27pt" in document_css
    assert "size: A4 portrait" in print_css
    assert "margin: 0" in print_css
