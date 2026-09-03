import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.redirect("/login")

	user = frappe.session.user
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.full_name = frappe.db.get_value("User", user, "full_name") or user

	customer = frappe.db.get_value("User Permission", {"user": user, "allow": "Customer"}, "for_value")
	supplier = frappe.db.get_value("User Permission", {"user": user, "allow": "Supplier"}, "for_value")
	context.customer = customer
	context.supplier = supplier
	context.default_country = frappe.db.get_default("country") or ""
	context.addresses = get_my_addresses(customer, supplier)
	return context


def _my_party_links():
	user = frappe.session.user
	customer = frappe.db.get_value("User Permission", {"user": user, "allow": "Customer"}, "for_value")
	supplier = frappe.db.get_value("User Permission", {"user": user, "allow": "Supplier"}, "for_value")
	links = []
	if customer:
		links.append(("Customer", customer))
	if supplier:
		links.append(("Supplier", supplier))
	return links


def get_my_addresses(customer, supplier):
	links = []
	if customer:
		links.append(("Customer", customer))
	if supplier:
		links.append(("Supplier", supplier))
	if not links:
		return []

	names = set()
	for link_doctype, link_name in links:
		names.update(frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": link_doctype, "link_name": link_name, "parenttype": "Address"},
			pluck="parent",
		))
	if not names:
		return []

	return frappe.get_all(
		"Address",
		filters={"name": ["in", list(names)]},
		fields=[
			"name", "address_title", "address_type", "address_line1", "address_line2",
			"city", "state", "country", "pincode", "phone", "is_primary_address", "is_shipping_address",
		],
		order_by="is_primary_address desc, modified desc",
	)


@frappe.whitelist()
def add_address(
	address_title, address_line1, city, country,
	address_line2=None, state=None, pincode=None, phone=None, is_shipping_address=0,
):
	links = _my_party_links()
	if not links:
		frappe.throw("No linked Customer/Supplier account found for this login.")

	doc = frappe.get_doc({
		"doctype": "Address",
		"address_title": address_title,
		"address_type": "Shipping" if int(is_shipping_address or 0) else "Billing",
		"address_line1": address_line1,
		"address_line2": address_line2,
		"city": city,
		"state": state,
		"country": country,
		"pincode": pincode,
		"phone": phone,
		"is_shipping_address": int(is_shipping_address or 0),
	})
	for link_doctype, link_name in links:
		doc.append("links", {"link_doctype": link_doctype, "link_name": link_name})
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def delete_address(address_name):
	allowed = set()
	for link_doctype, link_name in _my_party_links():
		allowed.update(frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": link_doctype, "link_name": link_name, "parenttype": "Address"},
			pluck="parent",
		))
	if address_name not in allowed:
		frappe.throw("Not permitted", frappe.PermissionError)
	frappe.delete_doc("Address", address_name, ignore_permissions=True)
