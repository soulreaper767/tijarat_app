import frappe


def auto_invoice_and_assign(doc, method=None):
	"""Sales Order on_submit. Orders still waiting on a Customer Service
	supplier fix (see marketplace._route_to_customer_service) aren't ready to
	bill yet, so those are skipped here - this only fires for orders that
	were clean enough to auto-submit in the first place. Creates and submits
	the Sales Invoice immediately (Tijarat bills on order, not on delivery),
	then hands it to a Sales Coordinator for the customer's territory so a
	human is on record as owning follow-up (payment chasing, delivery
	coordination) even though the invoice itself needed no manual input."""
	if doc.get("needs_supplier_assignment"):
		return

	invoice = _make_sales_invoice(doc)
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	coordinator = _resolve_territory_coordinator(doc.customer)
	if coordinator:
		_assign_invoice(invoice.name, doc.name, coordinator)
	else:
		frappe.log_error(
			title="Tijarat: no Sales Coordinator available",
			message=(
				f"Sales Invoice {invoice.name} (from Sales Order {doc.name}) has no "
				f"Sales Coordinator to assign - no territory in the customer's "
				f"territory/parent-territory chain has a territory_manager resolving "
				f"to an enabled user."
			),
		)

	frappe.db.commit()


def _make_sales_invoice(sales_order):
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	invoice = make_sales_invoice(sales_order.name, ignore_permissions=True)
	invoice.set_posting_time = 1
	return invoice


def _resolve_territory_coordinator(customer):
	"""Walks Customer.territory up its parent_territory chain, at each level
	checking Territory.territory_manager (Link -> Sales Person) -> Sales
	Person.employee -> Employee.user_id for an enabled user. This reuses
	territory_manager, a native field ERPNext ships but no native automation
	touches, and Territory's existing tree hierarchy for the "escalate to
	whoever covers the level above" behavior - no new schema needed."""
	territory = frappe.db.get_value("Customer", customer, "territory")

	seen = set()
	while territory and territory not in seen:
		seen.add(territory)
		manager, parent_territory = frappe.db.get_value(
			"Territory", territory, ["territory_manager", "parent_territory"]
		)
		user = _sales_person_to_user(manager) if manager else None
		if user:
			return user
		territory = parent_territory

	return None


def _sales_person_to_user(sales_person):
	employee = frappe.db.get_value("Sales Person", sales_person, "employee")
	if not employee:
		return None
	user = frappe.db.get_value("Employee", employee, "user_id")
	if user and frappe.db.get_value("User", user, "enabled"):
		return user
	return None


def _assign_invoice(invoice_name, sales_order_name, coordinator):
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": coordinator,
			"reference_type": "Sales Invoice",
			"reference_name": invoice_name,
			"priority": "Medium",
			"description": (
				f"Sales Invoice {invoice_name} was auto-created and submitted from "
				f"Sales Order {sales_order_name}. Follow up on payment and delivery "
				f"coordination for this territory."
			),
		}
	).insert(ignore_permissions=True)
