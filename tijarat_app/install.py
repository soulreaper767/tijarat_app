import frappe


def after_install():
	seed_customer_groups()
	enable_common_party_accounting()
	seed_territories()
	frappe.db.commit()


def after_migrate():
	# after_install-only seeding is fragile: it never re-runs once the app is
	# already installed, so nothing here gets repaired if a record is
	# accidentally deleted, or backfilled onto a site that installed an
	# older version of this app. Mirror after_install here too.
	seed_customer_groups()
	enable_common_party_accounting()
	seed_territories()
	frappe.db.commit()


# Territory is a native Frappe/ERPNext tree doctype - Tijarat's whole
# territory-matching model (see api/territory.py) runs on top of it, so this
# seeds the real Pakistan > Punjab > Lahore hierarchy plus Lahore's own
# main trade/commercial sub-territories, rather than leaving the tree empty.
TERRITORY_TREE = {
	"All Territories": {
		"is_group": 1,
		"parent": None,
		"children": {
			"Pakistan": {
				"is_group": 1,
				"children": {
					"Punjab": {
						"is_group": 1,
						"children": {
							"Lahore": {
								"is_group": 1,
								"children": {
									"Gulberg": {},
									"Model Town": {},
									"Johar Town": {},
									"DHA Lahore": {},
									"Iqbal Town": {},
									"Township": {},
									"Faisal Town": {},
									"Samanabad": {},
									"Shalimar": {},
									"Lahore Cantt": {},
									"Badami Bagh": {},
									"Shah Alam Market": {},
									"Walled City Lahore": {},
								},
							},
						},
					},
				},
			},
		},
	},
}


def seed_territories():
	def _create(name, parent, is_group):
		if frappe.db.exists("Territory", name):
			return
		frappe.get_doc({
			"doctype": "Territory",
			"territory_name": name,
			"parent_territory": parent,
			"is_group": 1 if is_group else 0,
		}).insert(ignore_permissions=True)

	def _walk(tree, parent=None):
		for name, cfg in tree.items():
			_create(name, parent, is_group=bool(cfg.get("children")))
			if cfg.get("children"):
				_walk(cfg["children"], parent=name)

	_walk(TERRITORY_TREE)


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
