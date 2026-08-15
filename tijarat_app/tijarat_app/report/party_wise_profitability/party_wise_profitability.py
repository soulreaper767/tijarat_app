import frappe
from frappe.utils import flt


def execute(filters=None):
	"""Which customers are actually profitable to the platform, not just
	high-volume - same net-profit formula as Deal Profitability
	(platform_commission_amount - referral_commission_amount), rolled up
	per Customer instead of left at one row per invoice."""
	filters = filters or {}
	columns = [
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 120},
		{"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": "Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": "Commission Earned", "fieldname": "commission", "fieldtype": "Currency", "width": 140},
		{"label": "Referral Payout", "fieldname": "referral_payout", "fieldtype": "Currency", "width": 130},
		{"label": "Net Profit", "fieldname": "net_profit", "fieldtype": "Currency", "width": 120},
		{"label": "Margin %", "fieldname": "margin_pct", "fieldtype": "Percent", "width": 100},
	]

	conditions = ["docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("territory"):
		conditions.append("territory = %(territory)s")
		values["territory"] = filters["territory"]

	data = frappe.db.sql(
		"""
		select customer, territory,
			   count(*) as invoice_count,
			   sum(grand_total) as revenue,
			   sum(platform_commission_amount) as commission,
			   sum(referral_commission_amount) as referral_payout
		from `tabSales Invoice`
		where {conditions}
		group by customer
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	for row in data:
		row["net_profit"] = flt(row.commission) - flt(row.referral_payout)
		row["margin_pct"] = round((row["net_profit"] / flt(row.revenue)) * 100, 2) if row.revenue else 0
	data.sort(key=lambda r: r["net_profit"], reverse=True)

	total_revenue = sum(flt(r.revenue) for r in data)
	total_net = sum(r["net_profit"] for r in data)
	report_summary = [
		{"value": len(data), "label": "Customers", "datatype": "Int", "indicator": "Blue"},
		{"value": total_revenue, "label": "Total Revenue", "datatype": "Currency", "indicator": "Purple"},
		{"value": total_net, "label": "Total Net Profit", "datatype": "Currency", "indicator": "Green"},
	]
	top = data[:10]
	chart = {
		"data": {
			"labels": [r.customer for r in top],
			"datasets": [{"name": "Net Profit", "values": [r["net_profit"] for r in top]}],
		},
		"type": "bar",
		"colors": ["#2E7D5B"],
	}
	return columns, data, None, chart, report_summary
