import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Who's actually booking orders - mainly interesting for Assisted
	bookings (Field Officers), but includes Self/Online so the full picture
	of where volume comes from is in one place."""
	filters = filters or {}
	columns = [
		{"label": "Booked By", "fieldname": "booked_by", "fieldtype": "Data", "width": 200},
		{"label": "Channel", "fieldname": "booking_channel", "fieldtype": "Data", "width": 100},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
	]

	conditions = ["docstatus = 1", "booked_by is not null", "booked_by != ''"]
	values = {}
	if filters.get("from_date"):
		conditions.append("transaction_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("transaction_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("booking_channel"):
		conditions.append("booking_channel = %(booking_channel)s")
		values["booking_channel"] = filters["booking_channel"]

	data = frappe.db.sql(
		"""
		select booked_by, booking_channel, count(*) as order_count, sum(grand_total) as revenue
		from `tabSales Order`
		where {conditions}
		group by booked_by, booking_channel
		order by revenue desc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)

	report_summary = [
		{"value": len(data), "label": "Active Bookers", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(r.order_count for r in data), "label": "Total Orders", "datatype": "Int", "indicator": "Purple"},
		{"value": sum(flt(r.revenue) for r in data), "label": "Total Revenue", "datatype": "Currency", "indicator": "Green"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r.booked_by for r in top],
			"datasets": [{"name": "Revenue", "values": [flt(r.revenue) for r in top]}],
		},
		"type": "bar",
		"colors": ["#1B3A5C"],
	}
	return columns, data, None, chart, report_summary
