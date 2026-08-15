import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Item-wise / by-SKU / by-volume / by-funds-value view - one consolidated
	report rather than four near-duplicates, since they're all the same
	underlying breakdown with a different sort order."""
	filters = filters or {}
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "Qty Sold", "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": "Avg Rate", "fieldname": "avg_rate", "fieldtype": "Currency", "width": 110},
	]

	conditions = ["si.docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("item"):
		conditions.append("sii.item_code = %(item)s")
		values["item"] = filters["item"]
	if filters.get("territory"):
		conditions.append("si.territory = %(territory)s")
		values["territory"] = filters["territory"]

	data = frappe.db.sql(
		"""
		select sii.item_code,
			   sii.item_name,
			   count(distinct si.name) as order_count,
			   sum(sii.qty) as qty,
			   sum(sii.amount) as revenue
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where {conditions}
		group by sii.item_code
		order by revenue desc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	for row in data:
		row["avg_rate"] = flt(row.revenue) / flt(row.qty) if row.qty else 0

	report_summary = [
		{"value": len(data), "label": "Distinct Items", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(flt(r.qty) for r in data), "label": "Total Qty Sold", "datatype": "Float", "indicator": "Purple"},
		{"value": sum(flt(r.revenue) for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Green"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r.item_name or r.item_code for r in top],
			"datasets": [{"name": "Revenue", "values": [flt(r.revenue) for r in top]}],
		},
		"type": "bar",
		"colors": ["#1B3A5C"],
	}
	return columns, data, None, chart, report_summary
