import frappe
from frappe import _

# Roles that legitimately need to see across every Field Officer's data -
# a Field Officer holding any of these too is never isolated.
_UNRESTRICTED_ROLES = ("Territory Manager", "Distributor Admin", "System Manager")


def _is_isolated_field_officer(user=None):
	"""True only for a user whose *sole* relevant role is Field Officer -
	a Territory Manager or Admin who also happens to carry the Field
	Officer role (e.g. covering for someone) is never restricted."""
	roles = frappe.get_roles(user)
	if "Field Officer" not in roles:
		return False
	return not any(r in roles for r in _UNRESTRICTED_ROLES)


def set_field_officer_default_workspace(doc, method=None):
	"""Frappe's get_home_page() resolves User.default_workspace before
	anything else - Role.home_page, Portal Settings, website_route_rules,
	whatever domain/login page was used to authenticate - so this is what
	actually decides where a Field Officer lands after login, regardless of
	entry point. Runs on every User save so it self-heals for any user who
	picks up the Field Officer role later, not just the ones seeded by
	seed_field_officers()."""
	roles = {r.role for r in doc.get("roles", [])}
	if "Field Officer" not in roles:
		return
	if any(r in roles for r in _UNRESTRICTED_ROLES):
		return
	if not doc.default_workspace:
		doc.default_workspace = "Field Officer"


def _own_sales_person(user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return None
	return frappe.db.get_value("Sales Person", {"employee": employee}, "name")


@frappe.whitelist()
def assign_field_officer_territories(sales_person, territories):
	"""Give a Field Officer (Sales Person) authority over one or more
	Territories - called by a Territory Manager/Platform Admin, not
	self-service (unlike api.territory.add_served_territory, which lets a
	Customer/Supplier manage their own record). Sets up two things:

	1. The Sales Person's own `served_territories` table (added as a
	   Custom Field, same Territory Coverage child table Customer/Supplier
	   already use) - for display, and for validate_customer_territory()
	   below to check against when this officer registers a new shop.
	2. A native Frappe User Permission per territory. Frappe's own
	   permission engine then automatically scopes every doctype with a
	   Territory link field (Customer, Sales Order, ...) to just these
	   territories for that officer - no custom list-filtering code needed
	   for those two doctypes.

	`territories` is a list (or JSON-encoded list) of Territory names.
	"""
	if isinstance(territories, str):
		territories = frappe.parse_json(territories)
	if not territories:
		frappe.throw(_("Give at least one territory to assign."))

	sp = frappe.get_doc("Sales Person", sales_person)
	if not sp.employee:
		frappe.throw(_("{0} has no linked Employee.").format(sales_person))
	user = frappe.db.get_value("Employee", sp.employee, "user_id")
	if not user:
		frappe.throw(_("The Employee linked to {0} has no linked User yet.").format(sales_person))

	existing = {row.territory for row in sp.get("served_territories", [])}
	for territory in territories:
		if territory not in existing:
			sp.append("served_territories", {
				"territory": territory,
				"is_primary": 1 if not existing else 0,
			})
			existing.add(territory)
	sp.save(ignore_permissions=True)

	if not frappe.db.exists(
		"User Permission", {"user": user, "allow": "Sales Person", "for_value": sales_person}
	):
		frappe.get_doc({
			"doctype": "User Permission", "user": user,
			"allow": "Sales Person", "for_value": sales_person,
		}).insert(ignore_permissions=True)

	for territory in territories:
		if not frappe.db.exists(
			"User Permission", {"user": user, "allow": "Territory", "for_value": territory}
		):
			frappe.get_doc({
				"doctype": "User Permission", "user": user,
				"allow": "Territory", "for_value": territory,
			}).insert(ignore_permissions=True)

	frappe.db.commit()
	return sorted(existing)


def validate_customer_territory(doc, method=None):
	"""A Field Officer can only register a new shop (Customer) inside one of
	their own assigned territories. Territory Managers/Admins are exempt -
	they're expected to operate across territories."""
	if not _is_isolated_field_officer():
		return
	if not doc.territory:
		return

	sales_person = _own_sales_person(frappe.session.user)
	allowed = []
	if sales_person:
		allowed = frappe.get_all(
			"Territory Coverage",
			filters={"parent": sales_person, "parenttype": "Sales Person"},
			pluck="territory",
		)
	if not allowed:
		frappe.throw(_(
			"You have not been assigned any territories yet - contact your Territory Manager."
		))
	if doc.territory not in allowed:
		frappe.throw(_(
			"You can only register shops in your assigned territories: {0}"
		).format(", ".join(allowed)))


def support_ticket_query_conditions(user):
	"""Field Officers only see the Support Tickets they personally raised;
	Support Agents/Distributor Admins/System Manager see everything."""
	if not _is_isolated_field_officer(user) or "Support Agent" in frappe.get_roles(user):
		return ""
	return f"`tabSupport Ticket`.raised_by = {frappe.db.escape(user)}"


def territory_exception_request_query_conditions(user):
	"""Field Officers only see the Territory Exception Requests they
	personally submitted; Territory Managers/Admins see everything."""
	if not _is_isolated_field_officer(user):
		return ""
	return f"`tabTerritory Exception Request`.owner = {frappe.db.escape(user)}"
