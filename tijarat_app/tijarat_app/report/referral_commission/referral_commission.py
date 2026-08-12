import frappe


def execute(filters=None):
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

	rows = frappe.get_all(
		"Referral Code",
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
	return columns, data
