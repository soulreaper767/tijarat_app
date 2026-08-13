import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.redirect("/login")

	context.no_cache = 1
	context.full_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	context.roles = frappe.get_roles(frappe.session.user)
	context.customer = frappe.db.get_value(
		"User Permission", {"user": frappe.session.user, "allow": "Customer"}, "for_value"
	)
	context.supplier = frappe.db.get_value(
		"User Permission", {"user": frappe.session.user, "allow": "Supplier"}, "for_value"
	)
	return context
