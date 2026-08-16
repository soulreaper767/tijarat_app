import frappe

# These two Custom DocPerm rows were shadowing Item Listing's own native
# permissions (System Manager, Distributor Admin, Field Officer, all
# defined directly in item_listing.json) - the moment any Custom DocPerm
# row exists for a doctype, Frappe stops consulting that doctype's built-in
# permissions table entirely and uses only the Custom DocPerm rows. Customer
# and Supplier access has been moved directly into item_listing.json's own
# permissions array instead. Fixture sync only inserts/updates, it never
# deletes, so removing these two rows from fixtures/custom_docperm.json
# doesn't remove them from an already-migrated site - this patch does that.
STALE_ROWS = ["tijarat-item-listing-customer", "tijarat-item-listing-supplier"]


def execute():
	for name in STALE_ROWS:
		if frappe.db.exists("Custom DocPerm", name):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Item Listing")
	frappe.db.commit()
