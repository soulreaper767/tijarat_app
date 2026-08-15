import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Net profit isn't stored per line item - platform_commission_amount and
	referral_commission_amount are invoice-level fields (api/commission.py
	accrues them once per Sales Invoice, not per item). So each item's
	profit here is its invoice's net profit, prorated by that item's share
	of the invoice's revenue - the standard way to attribute an
	invoice-level number down to line items without fabricating a
	per-item margin that doesn't actually exist in this platform's
	commission-based model."""
	filters = filters or {}
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Qty Sold", "fieldname": "qty", "fieldtype": "Float", "width": 100},
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

	items = frappe.db.sql(
		"""
		select sii.parent, sii.item_code, sii.item_name, sii.qty, sii.amount
		from `tabSales Invoice Item` sii
		where sii.parent in %(invoices)s
		""",
		{"invoices": list(invoice_map.keys())},
		as_dict=True,
	)

	item_data = {}
	for row in items:
		inv = invoice_map[row.parent]
		net_profit = flt(inv.platform_commission_amount) - flt(inv.referral_commission_amount)
		invoice_revenue = flt(inv.grand_total)
		share = (flt(row.amount) / invoice_revenue) if invoice_revenue else 0

		bucket = item_data.setdefault(
			row.item_code, {"item_code": row.item_code, "item_name": row.item_name, "qty": 0, "revenue": 0, "net_profit": 0}
		)
		bucket["qty"] += flt(row.qty)
		bucket["revenue"] += flt(row.amount)
		bucket["net_profit"] += net_profit * share

	data = list(item_data.values())
	for row in data:
		row["net_profit"] = round(row["net_profit"], 2)
		row["margin_pct"] = round((row["net_profit"] / row["revenue"]) * 100, 2) if row["revenue"] else 0
	data.sort(key=lambda r: r["net_profit"], reverse=True)

	report_summary = [
		{"value": len(data), "label": "Distinct Items", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(r["revenue"] for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Purple"},
		{"value": sum(r["net_profit"] for r in data), "label": "Total Net Profit", "datatype": "Currency", "indicator": "Green"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r["item_name"] or r["item_code"] for r in top],
			"datasets": [{"name": "Net Profit", "values": [r["net_profit"] for r in top]}],
		},
		"type": "bar",
		"colors": ["#E8A33D"],
	}
	return columns, data, None, chart, report_summary
