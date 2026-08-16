import frappe

from tijarat_app.api.catalog import publish_item_to_webshop


def execute():
	if not frappe.db.exists("DocType", "Website Item"):
		return

	published = 0
	failed = []

	for item_code in frappe.get_all("Item", filters={"disabled": 0}, pluck="name"):
		if frappe.db.exists("Website Item", {"item_code": item_code}):
			continue
		try:
			item_doc = frappe.get_doc("Item", item_code)
			if publish_item_to_webshop(item_doc):
				published += 1
		except Exception:
			failed.append(item_code)
			frappe.log_error(
				title="Tijarat: could not backfill Website Item",
				message=f"Item {item_code} - {frappe.get_traceback()}",
			)

	frappe.db.commit()

	if failed:
		frappe.log_error(
			title="Tijarat: Website Item backfill finished with failures",
			message=f"Published {published} Website Items; failed for: {', '.join(failed)}",
		)
