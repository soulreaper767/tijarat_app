import frappe


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
