import frappe


def execute(filters=None):
	filters = filters or {}
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

	conditions = ["1=1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("booked_on >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("booked_on <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("courier_partner"):
		conditions.append("courier_partner = %(courier_partner)s")
		values["courier_partner"] = filters["courier_partner"]

	rows = frappe.db.sql(
		"""
		select courier_partner,
			   count(*) as bookings,
			   sum(case when status = 'Delivered' then 1 else 0 end) as delivered,
			   sum(case when status = 'Failed' then 1 else 0 end) as failed,
			   sum(case when status = 'Returned' then 1 else 0 end) as returned
		from `tabCourier Booking`
		where {conditions}
		group by courier_partner
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	data = []
	for row in rows:
		row["delivered_pct"] = round((row.delivered / row.bookings) * 100, 1) if row.bookings else 0
		data.append(row)
	data.sort(key=lambda r: r["delivered_pct"], reverse=True)

	total_bookings = sum(r["bookings"] for r in data)
	total_delivered = sum(r["delivered"] for r in data)
	report_summary = [
		{"value": total_bookings, "label": "Bookings", "datatype": "Int", "indicator": "Blue"},
		{"value": total_delivered, "label": "Delivered", "datatype": "Int", "indicator": "Green"},
		{"value": sum(r["failed"] for r in data), "label": "Failed", "datatype": "Int", "indicator": "Red"},
		{
			"value": round((total_delivered / total_bookings) * 100, 1) if total_bookings else 0,
			"label": "Overall Delivered %",
			"datatype": "Percent",
			"indicator": "Orange",
		},
	]
	chart = {
		"data": {
			"labels": [r["courier_partner"] for r in data],
			"datasets": [{"name": "Delivered %", "values": [r["delivered_pct"] for r in data]}],
		},
		"type": "bar",
		"colors": ["#2C7A94"],
	}
	return columns, data, None, chart, report_summary
