import frappe


def after_install():
	bootstrap_erpnext_defaults()
	seed_customer_groups()
	enable_common_party_accounting()
	seed_territories()
	seed_field_officers()
	restrict_field_officer_workspaces()
	frappe.db.commit()


def after_migrate():
	# after_install-only seeding is fragile: it never re-runs once the app is
	# already installed, so nothing here gets repaired if a record is
	# accidentally deleted, or backfilled onto a site that installed an
	# older version of this app. Mirror after_install here too.
	bootstrap_erpnext_defaults()
	seed_customer_groups()
	enable_common_party_accounting()
	seed_territories()
	seed_field_officers()
	restrict_field_officer_workspaces()
	frappe.db.commit()


IRRELEVANT_WORKSPACES_FOR_FIELD_OFFICER = [
	"Build", "HR Setup", "Tenure", "Invoicing", "Recruitment", "Buying",
	"Financial Reports", "Selling", "Stock", "Performance", "Payroll",
	"Quality", "Tax & Benefits", "Projects", "Support", "Users", "Website",
	"CRM", "ERPNext Settings", "Integrations",
]


def restrict_field_officer_workspaces():
	"""Frappe's stock Workspace doctype grants full create/write/delete on
	Workspace to the built-in 'Desk User' role (auto-assigned to every
	System User), which is why any Field Officer could edit layouts or add
	new workspaces despite having no business reason to. Also: most of
	ERPNext/HRMS's own standard workspaces ship with an empty 'roles' table,
	which Frappe treats as visible to everyone - so a Field Officer's
	sidebar was showing Buying/Selling/Payroll/CRM/etc. alongside their own
	actual job. Neutralize both."""
	desk_user_perm = frappe.db.get_value(
		"DocPerm", {"parent": "Workspace", "role": "Desk User", "parenttype": "DocType"}, "name"
	)
	if desk_user_perm:
		frappe.db.set_value("DocPerm", desk_user_perm, {"write": 0, "create": 0, "delete": 0})

	existing = frappe.db.get_value(
		"Custom DocPerm", {"parent": "Workspace", "role": "System Manager"}, "name"
	)
	if not existing:
		frappe.get_doc({
			"doctype": "Custom DocPerm",
			"parent": "Workspace", "parenttype": "DocType", "parentfield": "permissions",
			"role": "System Manager", "permlevel": 0,
			"read": 1, "write": 1, "create": 1, "delete": 1,
			"report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
		}).insert(ignore_permissions=True)

	for name in IRRELEVANT_WORKSPACES_FOR_FIELD_OFFICER:
		if not frappe.db.exists("Workspace", name):
			continue
		existing_roles = {d.role for d in frappe.get_all(
			"Has Role", filters={"parent": name, "parenttype": "Workspace"}, fields=["role"]
		)}
		if existing_roles:
			# already scoped to something - don't fight whatever that is,
			# just make sure Field Officer specifically isn't in it
			if "Field Officer" in existing_roles:
				frappe.db.delete("Has Role", {
					"parent": name, "parenttype": "Workspace", "role": "Field Officer",
				})
			continue
		# empty roles table = visible to everyone; restrict to System Manager
		# only so it stops leaking to every role including Field Officer
		frappe.get_doc({
			"doctype": "Has Role", "parent": name, "parenttype": "Workspace",
			"parentfield": "roles", "role": "System Manager",
		}).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Workspace")


def bootstrap_erpnext_defaults():
	"""This site was created without ever running ERPNext's setup wizard, so
	none of the baseline masters normally created there exist yet - no
	Company, no root Customer/Supplier/Item Group nodes, no Fiscal Year, no
	Gender masters. seed_customer_groups() and every Employee/Sales
	Person/Customer creation depend on at least some of these, so this has
	to run before any of that."""
	for doctype, root_name, fieldname in (
		("Customer Group", "All Customer Groups", "customer_group_name"),
		("Supplier Group", "All Supplier Groups", "supplier_group_name"),
		("Item Group", "All Item Groups", "item_group_name"),
	):
		if not frappe.db.exists(doctype, root_name):
			frappe.get_doc({
				"doctype": doctype, fieldname: root_name, "is_group": 1,
			}).insert(ignore_permissions=True)

	for gender in ("Male", "Female", "Other", "Prefer not to say"):
		if not frappe.db.exists("Gender", gender):
			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)

	# Normally seeded by ERPNext's setup wizard (which never ran on this
	# site) - Company.on_update()'s create_default_warehouses() hard-depends
	# on "Transit" existing.
	for warehouse_type in ("Store", "Transit"):
		if not frappe.db.exists("Warehouse Type", warehouse_type):
			frappe.get_doc({"doctype": "Warehouse Type", "name": warehouse_type}).insert(ignore_permissions=True)

	# Sales Person is a NestedSet doctype that expects exactly one real root -
	# ERPNext's setup wizard normally creates this ("Sales Team", see
	# install_fixtures.py) which never ran on this site. Without it,
	# SalesPerson.validate()'s own `parent_sales_person = get_root_of(...)`
	# fallback has no genuine root to find and instead treats whichever
	# parentless Sales Person it hits first as "the root", corrupting the
	# tree and throwing NestedSetRecursionError the moment a second one is
	# saved. Every real Sales Person (Field Officers included) must nest
	# under this.
	if not frappe.db.exists("Sales Person", "Sales Team"):
		frappe.get_doc({
			"doctype": "Sales Person",
			"sales_person_name": "Sales Team",
			"is_group": 1,
			"parent_sales_person": "",
		}).insert(ignore_permissions=True)

	# Platform's own operating entity - not a marketplace Customer/Supplier -
	# needed as the Company on internal Employee/Sales Person records. Name
	# is a placeholder; rename the Company record directly if a different
	# legal name is wanted, nothing else keys off this specific string.
	company_name = "Tijarat"
	if not frappe.db.exists("Company", company_name):
		frappe.get_doc({
			"doctype": "Company",
			"company_name": company_name,
			"abbr": "TJR",
			"default_currency": "PKR",
			"country": "Pakistan",
		}).insert(ignore_permissions=True)
	if not frappe.db.get_default("company"):
		frappe.db.set_default("company", company_name)

	if not frappe.get_all("Fiscal Year", limit=1):
		# Pakistani businesses commonly run a July-June fiscal year.
		frappe.get_doc({
			"doctype": "Fiscal Year",
			"year": "2025-2026",
			"year_start_date": "2025-07-01",
			"year_end_date": "2026-06-30",
		}).insert(ignore_permissions=True)


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


FIELD_OFFICER_PASSWORD = "test123"
FIELD_OFFICERS = [
	# name, email, home territory (Route/visit-scheduling), all assigned territories
	("Field Officer - Gulberg", "fieldofficer.gulberg@tijarat.test", "Gulberg",
		["Gulberg", "Model Town"]),
	("Field Officer - Model Town", "fieldofficer.modeltown@tijarat.test", "Model Town",
		["Model Town", "Johar Town"]),
	("Field Officer - Johar Town", "fieldofficer.johartown@tijarat.test", "Johar Town",
		["Johar Town", "Faisal Town"]),
	("Field Officer - DHA", "fieldofficer.dha@tijarat.test", "DHA Lahore",
		["DHA Lahore", "Lahore Cantt"]),
	("Field Officer - Iqbal Town", "fieldofficer.iqbaltown@tijarat.test", "Iqbal Town",
		["Iqbal Town", "Township"]),
]


def seed_field_officers():
	"""One test User + Employee + Sales Person + a daily Route per Field
	Officer, each assigned more than one Lahore territory (see
	api.field_officer.assign_field_officer_territories), so the role can
	actually be logged into and tested - including the multi-territory
	assignment and the resulting data isolation - rather than existing only
	on paper."""
	from tijarat_app.api.field_officer import assign_field_officer_territories

	company = frappe.db.get_default("company") or frappe.db.get_value("Company", {}, "name")
	if not company:
		return

	for name, email, home_territory, territories in FIELD_OFFICERS:
		if not frappe.db.exists("User", email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": name,
				"send_welcome_email": 0,
				"enabled": 1,
				"user_type": "System User",
				"roles": [{"role": "Field Officer"}],
			})
			user.insert(ignore_permissions=True)
			frappe.utils.password.update_password(email, FIELD_OFFICER_PASSWORD)

		if not frappe.db.exists("Employee", {"user_id": email}):
			frappe.get_doc({
				"doctype": "Employee",
				"first_name": name,
				"employee_name": name,
				"company": company,
				"gender": "Prefer not to say",
				"date_of_birth": "1995-01-01",
				"date_of_joining": frappe.utils.today(),
				"status": "Active",
				"user_id": email,
			}).insert(ignore_permissions=True)
		employee_name = frappe.db.get_value("Employee", {"user_id": email}, "name")

		if not frappe.db.exists("Sales Person", name):
			frappe.get_doc({
				"doctype": "Sales Person",
				"sales_person_name": name,
				"employee": employee_name,
				"enabled": 1,
				# Nest under the single "Sales Team" root created in
				# bootstrap_erpnext_defaults() - see the comment there for why
				# leaving this unset corrupts the tree.
				"parent_sales_person": "Sales Team",
			}).insert(ignore_permissions=True)

		route_name = f"{name} - Daily Route"
		if not frappe.db.exists("Route", route_name):
			frappe.get_doc({
				"doctype": "Route",
				"route_name": route_name,
				"sales_person": name,
				"territory": home_territory,
				"is_active": 1,
				"repeat_on": "Daily",
			}).insert(ignore_permissions=True)

		assign_field_officer_territories(name, territories)


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
