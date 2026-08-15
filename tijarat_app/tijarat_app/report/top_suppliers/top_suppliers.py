import frappe
from frappe.utils import flt

SORT_FIELD = {"Revenue": "revenue", "Order Count": "order_count"}


def execute(filters=None):
	"""Best-performing sellers on the marketplace ("best partners") - ranked
	by the Sales Orders placed against their Item Listings (primary_supplier),
	which is how a seller's own sales are tracked in this marketplace model."""
	filters = filters or {}
	columns = [
		{"label": "Supplier", "fieldname": "primary_supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": "Active Listings", "fieldname": "active_listings", "fieldtype": "Int", "width": 110},
		{"label": "Tijarat Score", "fieldname": "tijarat_score", "fieldtype": "Int", "width": 100},
	]

	conditions = ["docstatus = 1", "primary_supplier is not null", "primary_supplier != ''"]
	values = {}
	if filters.get("from_date"):
		conditions.append("transaction_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("transaction_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	data = frappe.db.sql(
		"""
		select primary_supplier, count(*) as order_count, sum(grand_total) as revenue
		from `tabSales Order`
		where {conditions}
		group by primary_supplier
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)

	suppliers = [r.primary_supplier for r in data]
	listing_counts = {}
	scores = {}
	if suppliers:
		for row in frappe.get_all(
			"Item Listing", filters={"supplier": ["in", suppliers], "is_active": 1}, fields=["supplier"]
		):
			listing_counts[row.supplier] = listing_counts.get(row.supplier, 0) + 1
		scores = {
			r.name: r.tijarat_score
			for r in frappe.get_all("Supplier", filters={"name": ["in", suppliers]}, fields=["name", "tijarat_score"])
		}

	for row in data:
		row["active_listings"] = listing_counts.get(row.primary_supplier, 0)
		row["tijarat_score"] = scores.get(row.primary_supplier, 0)

	sort_field = SORT_FIELD.get(filters.get("sort_by"), "revenue")
	data.sort(key=lambda r: flt(r[sort_field]), reverse=True)

	report_summary = [
		{"value": len(data), "label": "Active Suppliers", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(flt(r.revenue) for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Green"},
		{"value": sum(r.order_count for r in data), "label": "Total Orders", "datatype": "Int", "indicator": "Purple"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r.primary_supplier for r in top],
			"datasets": [{"name": filters.get("sort_by") or "Revenue", "values": [flt(r[sort_field]) for r in top]}],
		},
		"type": "bar",
		"colors": ["#2C7A94"],
	}
	return columns, data, None, chart, report_summary
