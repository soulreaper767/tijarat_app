import frappe


def publish_new_item_to_webshop(doc, method=None):
	"""Item after_insert hook. Every new, sellable Item should be buyable
	from the storefront by default - creates and publishes its matching
	Website Item immediately. Wrapped defensively since this must never
	block Item creation itself if webshop isn't installed, the item is
	missing something Website Item requires, or the acting user lacks
	Website Item permissions - any of those just gets logged instead."""
	try:
		publish_item_to_webshop(doc)
	except Exception:
		frappe.log_error(
			title="Tijarat: could not auto-publish Item to webshop",
			message=f"Item {doc.name} - {frappe.get_traceback()}",
		)


def publish_item_to_webshop(item_doc):
	"""Shared by the after_insert hook above and the one-time backfill
	patch. Skips template variants themselves (variant_of set) - webshop's
	own product page already puts a Size/Color-style picker on the
	*template's* Website Item, so a variant getting its own separate
	storefront page would just be a confusing duplicate, not an
	additional product. Returns the created Website Item's name, or None
	if nothing was created (webshop not installed, already published, or
	this is a variant)."""
	if not frappe.db.exists("DocType", "Website Item"):
		return None
	if item_doc.get("variant_of"):
		return None
	if frappe.db.exists("Website Item", {"item_code": item_doc.item_code}):
		return None

	from webshop.webshop.doctype.website_item.website_item import make_website_item

	result = make_website_item(item_doc, save=True)
	website_item_name = result[0] if result else None
	if website_item_name:
		frappe.db.set_value("Website Item", website_item_name, "published", 1)
	return website_item_name


def apply_item_group_attributes(doc, method=None):
	"""Item validate hook. A new variant template (has_variants=1) under an
	industry Item Group should carry more than a generic name/description -
	pre-fill its attribute table from that Item Group's configured default
	attributes (Size/Color/Fabric for Textile & Apparel, Dosage Form for
	Pharmaceuticals, Material/Grade for Industrial, etc.) so whoever builds
	the variants already has the right structured fields instead of having
	to remember which attributes matter for that industry. Only runs when
	the attribute table is still empty, so it never overwrites attributes
	someone has already set up by hand."""
	if not doc.get("has_variants") or not doc.get("item_group") or doc.get("attributes"):
		return

	default_attributes = frappe.get_all(
		"Item Group Default Attribute",
		filters={"parent": doc.item_group, "parenttype": "Item Group"},
		fields=["attribute"],
		order_by="idx",
	)
	for row in default_attributes:
		doc.append("attributes", {"attribute": row.attribute})
