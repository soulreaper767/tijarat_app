import frappe


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 120},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Data", "width": 80},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": "Stock Status", "fieldname": "stock_status", "fieldtype": "Data", "width": 100},
		{"label": "Min Order Qty", "fieldname": "min_order_qty", "fieldtype": "Float", "width": 100},
		{"label": "Valid Upto", "fieldname": "valid_upto", "fieldtype": "Date", "width": 100},
	]

	conditions = ["l.is_active = 1"]
	values = {}
	if filters.get("item"):
		conditions.append("l.item = %(item)s")
		values["item"] = filters["item"]
	if filters.get("territory"):
		conditions.append("(l.territory = %(territory)s or l.territory is null or l.territory = '')")
		values["territory"] = filters["territory"]

	data = frappe.db.sql(
		"""
		select l.item, i.item_name, l.supplier, l.territory, l.rate, l.currency,
			   l.uom, l.stock_status, l.min_order_qty, l.valid_upto
		from `tabItem Listing` l
		left join `tabItem` i on i.name = l.item
		where {conditions}
		order by l.item asc, l.rate asc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	return columns, data
