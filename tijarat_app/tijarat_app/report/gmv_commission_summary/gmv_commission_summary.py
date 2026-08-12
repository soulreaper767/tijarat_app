import frappe


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
	return columns, data
