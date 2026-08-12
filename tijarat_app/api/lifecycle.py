import frappe
from frappe.utils import today


def mark_productive_customer(doc, method=None):
	_flip("Customer", doc.customer)


def mark_productive_supplier(doc, method=None):
	_flip("Supplier", doc.supplier)


def _flip(doctype, party_name):
	if not party_name:
		return
	status = frappe.db.get_value(doctype, party_name, "lifecycle_status")
	if status == "Registered":
		frappe.db.set_value(
			doctype,
			party_name,
			{"lifecycle_status": "Productive", "first_order_date": today()},
		)
