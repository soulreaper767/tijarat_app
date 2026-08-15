import frappe
from frappe.utils import flt


def execute(filters=None):
	"""P&L per deal, for the platform: net_profit = the commission Tijarat
	actually keeps (platform_commission_amount, accrued on submit - see
	api/commission.py) minus whatever referral payout that sale triggered.
	Tijarat doesn't buy/hold stock itself, so there's no COGS to net against
	revenue here - the deal's "profit" to the platform is its commission."""
	filters = filters or {}
	columns = [
		{"label": "Invoice", "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 130},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": "Deal Value", "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": "Platform Commission", "fieldname": "platform_commission_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Referral Payout", "fieldname": "referral_commission_amount", "fieldtype": "Currency", "width": 130},
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
	if filters.get("customer"):
		conditions.append("customer = %(customer)s")
		values["customer"] = filters["customer"]

	data = frappe.db.sql(
		"""
		select name, customer, posting_date, grand_total,
			   platform_commission_amount, referral_commission_amount
		from `tabSales Invoice`
		where {conditions}
		order by posting_date desc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	for row in data:
		row["net_profit"] = flt(row.platform_commission_amount) - flt(row.referral_commission_amount)
		row["margin_pct"] = round((row["net_profit"] / flt(row.grand_total)) * 100, 2) if row.grand_total else 0

	total_deal_value = sum(flt(r.grand_total) for r in data)
	total_commission = sum(flt(r.platform_commission_amount) for r in data)
	total_referral = sum(flt(r.referral_commission_amount) for r in data)
	total_net = total_commission - total_referral

	report_summary = [
		{"value": total_deal_value, "label": "Total Deal Value", "datatype": "Currency", "indicator": "Blue"},
		{"value": total_commission, "label": "Gross Commission", "datatype": "Currency", "indicator": "Purple"},
		{"value": total_referral, "label": "Referral Payout", "datatype": "Currency", "indicator": "Orange"},
		{"value": total_net, "label": "Net Profit", "datatype": "Currency", "indicator": "Green"},
	]
	chart = {
		"data": {
			"labels": [r.name for r in data[:15]],
			"datasets": [{"name": "Net Profit", "values": [flt(r.net_profit) for r in data[:15]]}],
		},
		"type": "bar",
		"colors": ["#2E7D5B"],
	}
	return columns, data, None, chart, report_summary
