import frappe
from frappe import _
from frappe.utils import cint


def validate_territory_lock(doc, method=None):
	"""Blocks a Sales Order if the customer's territory doesn't match the
	selling party's assigned territory, unless an approved exception exists.
	Runs as a `validate` hook, so it's synchronous and blocking - this is
	deliberately native Frappe logic, not routed through any external
	automation, per the project's stated rule that anything which must
	block a transaction stays server-side."""
	if not doc.customer:
		return

	customer_territory = frappe.db.get_value("Customer", doc.customer, "territory")
	if not customer_territory:
		return

	exclusivity = frappe.db.get_value("Territory", customer_territory, "exclusivity")
	if exclusivity != "Exclusive":
		return  # Shared territories don't enforce the lock

	selling_territory = _selling_territory(doc)
	if not selling_territory or selling_territory == customer_territory:
		return

	if _has_approved_exception(doc.customer, selling_territory):
		return

	frappe.throw(
		_(
			"This order crosses a territory boundary: the customer is in "
			"{0}, but this order is being placed against a seller assigned "
			"to {1}. Request a Territory Exception if this is intentional."
		).format(customer_territory, selling_territory)
	)


def _selling_territory(doc):
	# In a single-company pilot, the "selling territory" is best inferred
	# from the Item Listing chosen on each line (which carries its own
	# Territory) rather than from doc.territory directly, since Sales Order
	# doesn't have a native concept of "seller's territory" - only the
	# buyer's. Falls back to None (no check) if lines don't carry listings,
	# e.g. orders created outside the marketplace booking flow.
	territories = set()
	for item in doc.get("items", []):
		listing_name = item.get("item_listing")
		if listing_name:
			t = frappe.db.get_value("Item Listing", listing_name, "territory")
			if t:
				territories.add(t)
	if len(territories) == 1:
		return territories.pop()
	return None


def _has_approved_exception(customer, supplier_territory):
	return frappe.db.exists(
		"Territory Exception Request",
		{
			"customer": customer,
			"supplier_territory": supplier_territory,
			"workflow_state": "Approved",
		},
	)


@frappe.whitelist()
def request_exception(customer, requested_supplier, supplier_territory, reason):
	"""Raised from the app when validate_territory_lock blocks an order and
	the Field Officer/Distributor believes an exception is warranted. Goes
	to a Territory Manager for approval via the Workflow fixture."""
	doc = frappe.get_doc(
		{
			"doctype": "Territory Exception Request",
			"customer": customer,
			"requested_supplier": requested_supplier,
			"supplier_territory": supplier_territory,
			"reason": reason,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def add_served_territory(party_type, party_name, territory, is_primary=0):
	"""How a party with more than one territory is actually represented:
	Customer/Supplier both carry a `served_territories` table (seeded with
	their home territory at registration) rather than a single field, since
	a distributor/manufacturer routinely expands into new regions without
	ever leaving their original one. This is the self-service way they
	register that expansion; Item Listing (see item_listing.py's
	auto_mark_territory) defaults new listings from the primary entry here
	when a territory isn't picked explicitly.

	Goes through normal permission checks (not ignore_permissions), so a
	self-service caller can only touch their own Customer/Supplier record -
	the same User Permission set up at registration that scopes everything
	else about their account.
	"""
	if party_type not in ("Customer", "Supplier"):
		frappe.throw(_("party_type must be Customer or Supplier."))

	doc = frappe.get_doc(party_type, party_name)

	if any(row.territory == territory for row in doc.get("served_territories", [])):
		return doc.name

	if cint(is_primary):
		for row in doc.get("served_territories", []):
			row.is_primary = 0

	doc.append("served_territories", {"territory": territory, "is_primary": cint(is_primary)})
	doc.save()
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def list_served_territories(party_type, party_name):
	"""Every territory a party is registered to serve, primary first - what
	the frontend shows on a "your territories" screen and offers as
	Item Listing territory choices."""
	if party_type not in ("Customer", "Supplier"):
		frappe.throw(_("party_type must be Customer or Supplier."))

	# frappe.get_all bypasses permissions, so the read-check on the *parent*
	# record is done explicitly here rather than relying on it implicitly -
	# Territory Coverage is a child table and has no DocPerm of its own.
	if not frappe.has_permission(party_type, "read", party_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return frappe.get_all(
		"Territory Coverage",
		filters={"parent": party_name, "parenttype": party_type},
		fields=["territory", "is_primary"],
		order_by="is_primary desc, territory asc",
	)
