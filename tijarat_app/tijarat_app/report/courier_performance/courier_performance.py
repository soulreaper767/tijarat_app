import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Courier Partner",
			"fieldname": "courier_partner",
			"fieldtype": "Link",
			"options": "Courier Partner",
			"width": 160,
		},
		{"label": "Bookings", "fieldname": "bookings", "fieldtype": "Int", "width": 90},
		{"label": "Delivered", "fieldname": "delivered", "fieldtype": "Int", "width": 90},
		{"label": "Failed", "fieldname": "failed", "fieldtype": "Int", "width": 90},
		{"label": "Returned", "fieldname": "returned", "fieldtype": "Int", "width": 90},
		{"label": "Delivered %", "fieldname": "delivered_pct", "fieldtype": "Percent", "width": 110},
	]

	rows = frappe.db.sql(
		"""
		select courier_partner,
			   count(*) as bookings,
			   sum(case when status = 'Delivered' then 1 else 0 end) as delivered,
			   sum(case when status = 'Failed' then 1 else 0 end) as failed,
			   sum(case when status = 'Returned' then 1 else 0 end) as returned
		from `tabCourier Booking`
		group by courier_partner
		""",
		as_dict=True,
	)
	data = []
	for row in rows:
		row["delivered_pct"] = round((row.delivered / row.bookings) * 100, 1) if row.bookings else 0
		data.append(row)
	return columns, data
