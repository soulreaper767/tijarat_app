import frappe


def after_install():
	seed_customer_groups()
	enable_common_party_accounting()
	frappe.db.commit()


def seed_customer_groups():
	"""Retailer / Distributor / Wholesaler / Manufacturer are seeded as
	Customer Groups under the native root group - no custom doctype needed,
	Customer Group is already a native Frappe/ERPNext tree."""
	parent = "All Customer Groups"
	if not frappe.db.exists("Customer Group", parent):
		# Extremely unlikely on a real ERPNext install, but fail safe rather
		# than error out the whole install over this one cosmetic step.
		return

	groups = ["Retailer", "Distributor", "Wholesaler", "Manufacturer / Importer", "E-commerce"]
	for group_name in groups:
		if not frappe.db.exists("Customer Group", group_name):
			frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": group_name,
					"parent_customer_group": parent,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def enable_common_party_accounting():
	"""The native mechanism that lets a business be both a Customer and a
	Supplier with automatically netted ledgers - see register_trade_party()
	in api/registration.py, which creates a Party Link for every new party."""
	frappe.db.set_single_value("Accounts Settings", "enable_common_party_accounting", 1)
