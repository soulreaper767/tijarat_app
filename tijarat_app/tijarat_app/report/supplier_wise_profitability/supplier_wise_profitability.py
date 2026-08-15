import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Same attribution logic as SKU-Wise Profitability, resolved to the
	seller behind each line instead of the item: Sales Invoice Item.sales_order
	-> Sales Order.primary_supplier identifies who fulfilled that line
	(a Sales Order can only have one supplier - see book_order in
	api/marketplace.py), and each line's share of its invoice's net profit
	is prorated by revenue the same way."""
	filters = filters or {}
	columns = [
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": "Attributed Net Profit", "fieldname": "net_profit", "fieldtype": "Currency", "width": 160},
		{"label": "Margin %", "fieldname": "margin_pct", "fieldtype": "Percent", "width": 100},
	]

	conditions = ["si.docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	invoices = frappe.db.sql(
		"""
		select si.name, si.grand_total, si.platform_commission_amount, si.referral_commission_amount
		from `tabSales Invoice` si
		where {conditions}
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	invoice_map = {i.name: i for i in invoices}
	if not invoice_map:
		return columns, [], None, None, []

	lines = frappe.db.sql(
		"""
		select sii.parent, sii.amount, so.primary_supplier, so.name as sales_order
		from `tabSales Invoice Item` sii
		join `tabSales Order` so on so.name = sii.sales_order
		where sii.parent in %(invoices)s and so.primary_supplier is not null and so.primary_supplier != ''
		""",
		{"invoices": list(invoice_map.keys())},
		as_dict=True,
	)

	supplier_data = {}
	order_seen = {}
	for row in lines:
		inv = invoice_map[row.parent]
		net_profit = flt(inv.platform_commission_amount) - flt(inv.referral_commission_amount)
		invoice_revenue = flt(inv.grand_total)
		share = (flt(row.amount) / invoice_revenue) if invoice_revenue else 0

		bucket = supplier_data.setdefault(row.primary_supplier, {"supplier": row.primary_supplier, "revenue": 0, "net_profit": 0})
		bucket["revenue"] += flt(row.amount)
		bucket["net_profit"] += net_profit * share
		order_seen.setdefault(row.primary_supplier, set()).add(row.sales_order)

	data = list(supplier_data.values())
	for row in data:
		row["order_count"] = len(order_seen.get(row["supplier"], []))
		row["net_profit"] = round(row["net_profit"], 2)
		row["margin_pct"] = round((row["net_profit"] / row["revenue"]) * 100, 2) if row["revenue"] else 0
	data.sort(key=lambda r: r["net_profit"], reverse=True)

	report_summary = [
		{"value": len(data), "label": "Suppliers", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(r["revenue"] for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Purple"},
		{"value": sum(r["net_profit"] for r in data), "label": "Total Net Profit", "datatype": "Currency", "indicator": "Green"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r["supplier"] for r in top],
			"datasets": [{"name": "Net Profit", "values": [r["net_profit"] for r in top]}],
		},
		"type": "bar",
		"colors": ["#2C7A94"],
	}
	return columns, data, None, chart, report_summary
