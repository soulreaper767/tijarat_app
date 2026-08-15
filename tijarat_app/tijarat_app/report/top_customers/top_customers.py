import frappe
from frappe.utils import flt

SORT_FIELD = {"Revenue": "revenue", "Quantity": "qty", "Order Count": "order_count"}


def execute(filters=None):
	""""Best shops to buy the most" / "top performing customers", ranked by
	revenue, quantity, or order count - one report, three lenses, rather than
	three near-identical reports."""
	filters = filters or {}
	columns = [
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 120},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": "Tijarat Score", "fieldname": "tijarat_score", "fieldtype": "Int", "width": 100},
	]

	conditions = ["si.docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("territory"):
		conditions.append("si.territory = %(territory)s")
		values["territory"] = filters["territory"]

	# Revenue/order_count computed from Sales Invoice directly (not joined
	# against Sales Invoice Item) so a multi-line invoice doesn't inflate
	# grand_total by counting it once per item row; quantity is fetched
	# separately below for exactly that reason.
	data = frappe.db.sql(
		"""
		select si.customer,
			   si.territory,
			   count(*) as order_count,
			   sum(si.grand_total) as revenue
		from `tabSales Invoice` si
		where {conditions}
		group by si.customer
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	qty_by_customer = frappe.db.sql(
		"""
		select si.customer, sum(sii.qty) as qty
		from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		where {conditions}
		group by si.customer
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	qty_map = {r.customer: flt(r.qty) for r in qty_by_customer}
	scores = {
		r.name: r.tijarat_score
		for r in frappe.get_all("Customer", filters={"name": ["in", [d.customer for d in data]]}, fields=["name", "tijarat_score"])
	} if data else {}

	for row in data:
		row["qty"] = qty_map.get(row.customer, 0)
		row["tijarat_score"] = scores.get(row.customer, 0)

	sort_field = SORT_FIELD.get(filters.get("sort_by"), "revenue")
	data.sort(key=lambda r: flt(r[sort_field]), reverse=True)

	report_summary = [
		{"value": len(data), "label": "Active Customers", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(flt(r.revenue) for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Green"},
		{"value": sum(r.order_count for r in data), "label": "Total Orders", "datatype": "Int", "indicator": "Purple"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r.customer for r in top],
			"datasets": [{"name": filters.get("sort_by") or "Revenue", "values": [flt(r[sort_field]) for r in top]}],
		},
		"type": "bar",
		"colors": ["#E8A33D"],
	}
	return columns, data, None, chart, report_summary
