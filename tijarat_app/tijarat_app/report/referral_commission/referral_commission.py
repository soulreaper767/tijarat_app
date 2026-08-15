import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Referral Code", "fieldname": "code", "fieldtype": "Link", "options": "Referral Code", "width": 140},
		{"label": "Referrer Type", "fieldname": "referrer_type", "fieldtype": "Data", "width": 220},
		{"label": "Referrer", "fieldname": "referrer", "fieldtype": "Data", "width": 160},
		{"label": "Times Used", "fieldname": "times_used", "fieldtype": "Int", "width": 100},
		{
			"label": "Commission Earned",
			"fieldname": "total_commission_earned",
			"fieldtype": "Currency",
			"width": 150,
		},
	]

	report_filters = {}
	if filters.get("referrer_type"):
		report_filters["referrer_type"] = filters["referrer_type"]

	rows = frappe.get_all(
		"Referral Code",
		filters=report_filters,
		fields=[
			"code",
			"referrer_type",
			"sales_person",
			"sales_partner",
			"times_used",
			"total_commission_earned",
		],
		order_by="total_commission_earned desc",
	)
	data = []
	for row in rows:
		row["referrer"] = row.sales_person or row.sales_partner
		data.append(row)

	top = data[:10]
	report_summary = [
		{"value": len(data), "label": "Active Codes", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(r.times_used or 0 for r in data), "label": "Total Uses", "datatype": "Int", "indicator": "Purple"},
		{
			"value": sum(flt(r.total_commission_earned) for r in data),
			"label": "Commission Paid",
			"datatype": "Currency",
			"indicator": "Orange",
		},
	]
	chart = {
		"data": {
			"labels": [r.referrer or r.code for r in top],
			"datasets": [{"name": "Commission Earned", "values": [flt(r.total_commission_earned) for r in top]}],
		},
		"type": "bar",
		"colors": ["#E8A33D"],
	}
	return columns, data, None, chart, report_summary
