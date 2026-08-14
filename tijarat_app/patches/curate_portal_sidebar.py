import frappe

# ERPNext's own standard_portal_menu_items hook injects generic B2B
# procurement items (Projects, RFQs, Supplier Quotations, Timesheets,
# Material Request, Newsletter...) that don't apply to Tijarat's actual
# marketplace. Since every Tijarat account holds both Customer and
# Supplier roles, a user would otherwise see nearly the entire generic
# list. hide_standard_menu switches that off in favour of a short,
# curated menu that only points at pages that actually exist/apply.
CUSTOM_MENU = [
	{"title": "Dashboard", "route": "/home", "enabled": 1},
	{"title": "My Orders", "route": "/orders", "reference_doctype": "Sales Order", "enabled": 1},
	{"title": "My Deliveries", "route": "/shipments", "reference_doctype": "Delivery Note", "enabled": 1},
	{"title": "My Addresses", "route": "/addresses", "reference_doctype": "Address", "enabled": 1},
	{"title": "My Profile", "route": "/me", "enabled": 1},
]


def execute():
	settings = frappe.get_single("Portal Settings")
	settings.hide_standard_menu = 1
	settings.default_portal_home = "/home"
	settings.set("custom_menu", [])
	for row in CUSTOM_MENU:
		settings.append("custom_menu", row)
	settings.save(ignore_permissions=True)
	frappe.db.commit()
