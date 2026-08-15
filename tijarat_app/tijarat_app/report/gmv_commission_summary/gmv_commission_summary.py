import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 180},
		{"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": "GMV", "fieldname": "gmv", "fieldtype": "Currency", "width": 130},
		{"label": "Platform Commission", "fieldname": "platform_commission", "fieldtype": "Currency", "width": 150},
		{"label": "Referral Commission", "fieldname": "referral_commission", "fieldtype": "Currency", "width": 150},
	]

	conditions = ["docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters["company"]

	data = frappe.db.sql(
		"""
		select company,
			   count(*) as invoice_count,
			   sum(grand_total) as gmv,
			   sum(platform_commission_amount) as platform_commission,
			   sum(referral_commission_amount) as referral_commission
		from `tabSales Invoice`
		where {conditions}
		group by company
		order by gmv desc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)

	total_gmv = sum(flt(r.gmv) for r in data)
	total_platform = sum(flt(r.platform_commission) for r in data)
	total_referral = sum(flt(r.referral_commission) for r in data)
	total_invoices = sum(r.invoice_count for r in data)

	report_summary = [
		{"value": total_invoices, "label": "Invoices", "datatype": "Int", "indicator": "Blue"},
		{"value": total_gmv, "label": "Total GMV", "datatype": "Currency", "indicator": "Green"},
		{"value": total_platform, "label": "Platform Commission", "datatype": "Currency", "indicator": "Orange"},
		{"value": total_referral, "label": "Referral Commission", "datatype": "Currency", "indicator": "Purple"},
	]

	chart = {
		"data": {
			"labels": [r.company for r in data],
			"datasets": [{"name": "GMV", "values": [flt(r.gmv) for r in data]}],
		},
		"type": "bar",
		"colors": ["#1B3A5C"],
	}

	return columns, data, None, chart, report_summary
