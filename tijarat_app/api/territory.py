import frappe
from frappe import _


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
