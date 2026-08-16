import frappe

ITEM_GROUPS = [
	{
		"name": "Food, Beverage & FMCG",
		"children": [
			"FMCG & Grocery",
			"Beverages",
			"Confectionery & Snacks",
			"Dairy & Frozen Foods",
			"HORECA & Foodservice",
		],
	},
	{
		"name": "Fashion & Textile",
		"children": ["Textile & Apparel", "Footwear", "Leather Goods", "Fashion Accessories"],
	},
	{
		"name": "Health & Beauty",
		"children": ["Pharmaceuticals & Healthcare", "Cosmetics & Personal Care", "Medical Equipment & Supplies"],
	},
	{
		"name": "Industrial & Manufacturing",
		"children": ["Automobile & Auto Parts", "Engineering & Hardware", "Plastics", "Packaging Materials", "Chemicals"],
	},
	{
		"name": "Home & Lifestyle",
		"children": [
			"Furniture & Home Decor",
			"Electronics & Appliances",
			"Sports & Fitness Equipment",
			"Stationery & Office Supplies",
		],
	},
]

# Global attribute registry - deliberately reused across unrelated Item
# Groups where the concept genuinely overlaps (Pack Size, Color, Material)
# rather than defining near-duplicate attributes per group.
ITEM_ATTRIBUTES = {
	"Pack Size": ["100ml", "250ml", "500ml", "1L", "1.5L", "5L", "100g", "250g", "500g", "1kg", "5kg", "10kg"],
	"Flavor": ["Original", "Mint", "Lemon", "Mixed Fruit", "Chocolate", "Vanilla", "Unflavored"],
	"Storage Type": ["Ambient", "Chilled", "Frozen"],
	"Size": ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "Free Size"],
	"Color": ["Black", "White", "Red", "Blue", "Green", "Yellow", "Grey", "Navy", "Beige", "Brown", "Multicolor"],
	"Fabric Type": ["Cotton", "Polyester", "Silk", "Denim", "Leather", "Wool", "Linen", "Blended"],
	"Dosage Form": ["Tablet", "Capsule", "Syrup", "Injection", "Cream", "Ointment", "Drops"],
	"Skin/Hair Type": ["All Types", "Oily", "Dry", "Sensitive", "Combination"],
	"Material": ["Steel", "Aluminum", "Iron", "Copper", "Brass", "Wood", "Plastic", "Glass", "Rubber", "Composite", "Fabric", "Leather"],
	"Grade": ["Grade A", "Grade B", "Industrial Grade", "Food Grade", "ISO Certified"],
	"Size Category": ["Compact", "Standard", "Large", "Extra Large"],
}

# Which of the above attributes describe a variant template under each leaf
# Item Group - consumed by api.catalog.apply_item_group_attributes to
# pre-fill a new template's attribute table.
GROUP_ATTRIBUTES = {
	"FMCG & Grocery": ["Pack Size"],
	"Beverages": ["Pack Size", "Flavor", "Storage Type"],
	"Confectionery & Snacks": ["Pack Size", "Flavor"],
	"Dairy & Frozen Foods": ["Pack Size", "Storage Type"],
	"HORECA & Foodservice": ["Pack Size", "Storage Type"],
	"Textile & Apparel": ["Size", "Color", "Fabric Type"],
	"Footwear": ["Size", "Color"],
	"Leather Goods": ["Color", "Material"],
	"Fashion Accessories": ["Color", "Material"],
	"Pharmaceuticals & Healthcare": ["Dosage Form", "Pack Size"],
	"Cosmetics & Personal Care": ["Pack Size", "Skin/Hair Type"],
	"Medical Equipment & Supplies": ["Size Category", "Material"],
	"Automobile & Auto Parts": ["Material", "Grade"],
	"Engineering & Hardware": ["Material", "Grade", "Size Category"],
	"Plastics": ["Material", "Grade", "Color"],
	"Packaging Materials": ["Material", "Size Category"],
	"Chemicals": ["Grade", "Pack Size"],
	"Furniture & Home Decor": ["Material", "Color", "Size Category"],
	"Electronics & Appliances": ["Color", "Size Category"],
	"Sports & Fitness Equipment": ["Size", "Material", "Color"],
	"Stationery & Office Supplies": ["Color", "Pack Size"],
}


def execute():
	_ensure_default_attributes_field()
	_create_item_attributes()
	_create_item_groups()
	_map_group_attributes()
	frappe.db.commit()


def _ensure_default_attributes_field():
	"""fixtures/custom_field.json isn't synced onto the site until the
	post_schema_updates step of `bench migrate`, which runs after every
	post_model_sync patch (this one included) - so Item Group.
	default_item_attributes can't be relied on to exist yet. Create it here
	directly so _map_group_attributes() below has somewhere to write to; the
	fixture entry still keeps it in place on future installs/re-syncs."""
	name = "Item Group-default_item_attributes"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Item Group",
			"fieldname": "default_item_attributes",
			"label": "Default Item Attributes",
			"fieldtype": "Table",
			"options": "Item Group Default Attribute",
			"insert_after": "item_group_name",
			"name": name,
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Item Group")


def _create_item_attributes():
	for attribute_name, values in ITEM_ATTRIBUTES.items():
		if frappe.db.exists("Item Attribute", attribute_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Item Attribute",
				"attribute_name": attribute_name,
				"item_attribute_values": [{"attribute_value": v, "abbr": _abbr(v)} for v in values],
			}
		).insert(ignore_permissions=True)


def _abbr(value):
	"""Item Attribute Value's abbr must be unique per attribute and is used
	in generated variant item codes - a short, code-safe token derived from
	the value itself."""
	return "".join(ch for ch in value.upper() if ch.isalnum())[:8] or "NA"


def _create_item_groups():
	root = "All Item Groups"
	if not frappe.db.exists("Item Group", root):
		frappe.log_error(
			title="Tijarat: Item Group root missing",
			message="'All Item Groups' does not exist - cannot seed the industry taxonomy under it.",
		)
		return

	for group in ITEM_GROUPS:
		_ensure_item_group(group["name"], root, is_group=1)
		for child in group["children"]:
			_ensure_item_group(child, group["name"], is_group=0)


def _ensure_item_group(name, parent, is_group):
	if frappe.db.exists("Item Group", name):
		return
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"parent_item_group": parent,
			"is_group": is_group,
		}
	).insert(ignore_permissions=True)


def _map_group_attributes():
	for group_name, attribute_names in GROUP_ATTRIBUTES.items():
		if not frappe.db.exists("Item Group", group_name):
			continue
		doc = frappe.get_doc("Item Group", group_name)
		existing = {row.attribute for row in (doc.default_item_attributes or [])}
		changed = False
		for attribute_name in attribute_names:
			if attribute_name not in existing:
				doc.append("default_item_attributes", {"attribute": attribute_name})
				changed = True
		if changed:
			doc.save(ignore_permissions=True)
