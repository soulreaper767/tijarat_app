import frappe
from frappe import _


def validate_mrp_ceiling(doc, method=None):
	"""Blocks any Sales Invoice line whose rate exceeds the Item's declared
	MRP ceiling. Runs as a `validate` hook - synchronous and blocking,
	consistent with treating pricing discipline the same way territory lock
	is treated: never routed through anything external or async."""
	for item in doc.get("items", []):
		mrp_ceiling = frappe.db.get_value("Item", item.item_code, "mrp_ceiling")
		if mrp_ceiling and item.rate and item.rate > mrp_ceiling:
			frappe.throw(
				_("Row #{0}: Rate {1} for {2} exceeds its MRP ceiling of {3}.").format(
					item.idx, item.rate, item.item_code, mrp_ceiling
				)
			)


def apply_service_package_charges(doc, method=None):
	"""If a Service Package is attached to a Sales Order, adds each
	component (warehousing, delivery, insurance, etc.) as an additional
	charge - modeled as Sales Taxes and Charges rows of type Actual, so
	they're visible, itemized, and flow through to the eventual invoice
	rather than being folded silently into item rates."""
	if not doc.get("service_package"):
		return

	# Avoid double-adding on every save - only add charges not already present.
	existing_descriptions = {row.description for row in doc.get("taxes", [])}

	components = frappe.get_all(
		"Service Package Item",
		filters={"parent": doc.service_package},
		fields=["service_type", "description", "rate", "charge_type"],
	)

	default_account = frappe.db.get_value(
		"Company", doc.company, "default_income_account"
	) if doc.get("company") else None

	if components and not default_account:
		frappe.msgprint(
			_(
				"Service Package charges could not be added: no default income "
				"account is configured for this Company. Set one in Company "
				"settings, or add these charges manually."
			),
			alert=True,
		)
		return

	for component in components:
		label = component.description or component.service_type
		if label in existing_descriptions:
			continue

		charge_amount = component.rate
		if component.charge_type == "Percentage of Order Value":
			base = sum((row.amount or 0) for row in doc.get("items", []))
			charge_amount = base * (component.rate / 100)

		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": default_account,
				"description": f"{component.service_type}: {label}",
				"tax_amount": charge_amount,
			},
		)
