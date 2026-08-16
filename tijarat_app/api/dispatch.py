import frappe


def auto_assign_courier(doc, method=None):
	"""Delivery Note on_submit. Picks a Courier Partner whose served_territories
	covers the shipment's territory and books it automatically - the whole
	point of the new structured field over the old free-text coverage notes
	is that this match can be done in code instead of a human reading notes."""
	if frappe.db.exists("Courier Booking", {"delivery_note": doc.name}):
		return

	territory = doc.get("territory") or frappe.db.get_value("Customer", doc.customer, "territory")
	courier = _resolve_courier(territory)
	if not courier:
		frappe.log_error(
			title="Tijarat: no courier available for dispatch",
			message=(
				f"Delivery Note {doc.name} (territory {territory}) has no active "
				f"Courier Partner whose served territories cover it - book one manually."
			),
		)
		return

	sales_order = _first_sales_order(doc)
	frappe.get_doc(
		{
			"doctype": "Courier Booking",
			"sales_order": sales_order,
			"delivery_note": doc.name,
			"courier_partner": courier,
			"status": "Booked",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()


def _resolve_courier(territory):
	"""Prefers a courier whose served_territories row is flagged primary for
	this territory; falls back to any active courier serving it; cheapest
	base_rate breaks ties either way."""
	if not territory:
		return None

	rows = frappe.get_all(
		"Territory Coverage",
		filters={"territory": territory, "parenttype": "Courier Partner"},
		fields=["parent", "is_primary"],
	)
	if not rows:
		return None

	active_couriers = {
		c.name: c.base_rate
		for c in frappe.get_all(
			"Courier Partner",
			filters={"name": ["in", [r.parent for r in rows]], "is_active": 1},
			fields=["name", "base_rate"],
		)
	}
	if not active_couriers:
		return None

	primary = [r.parent for r in rows if r.is_primary and r.parent in active_couriers]
	pool = primary or [r.parent for r in rows if r.parent in active_couriers]
	return min(pool, key=lambda c: active_couriers.get(c) or 0)


def _first_sales_order(delivery_note):
	for item in delivery_note.get("items", []):
		if item.get("against_sales_order"):
			return item.against_sales_order
	return None
