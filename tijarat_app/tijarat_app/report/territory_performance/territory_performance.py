import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "GMV", "fieldname": "gmv", "fieldtype": "Currency", "width": 130},
		{"label": "Net Profit", "fieldname": "net_profit", "fieldtype": "Currency", "width": 120},
		{"label": "Open Territory Exceptions", "fieldname": "open_exceptions", "fieldtype": "Int", "width": 170},
	]

	conditions = ["so.docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("so.transaction_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("so.transaction_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	orders = frappe.db.sql(
		"""
		select c.territory as territory, count(*) as order_count, sum(so.grand_total) as gmv
		from `tabSales Order` so
		join `tabCustomer` c on c.name = so.customer
		where {conditions}
		group by c.territory
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	exceptions = frappe.db.sql(
		"""
		select supplier_territory as territory, count(*) as open_exceptions
		from `tabTerritory Exception Request`
		where workflow_state = 'Pending'
		group by supplier_territory
		""",
		as_dict=True,
	)
	exception_map = {row.territory: row.open_exceptions for row in exceptions if row.territory}

	profit_conditions = ["docstatus = 1"]
	profit_values = {}
	if filters.get("from_date"):
		profit_conditions.append("posting_date >= %(from_date)s")
		profit_values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		profit_conditions.append("posting_date <= %(to_date)s")
		profit_values["to_date"] = filters["to_date"]
	profit_rows = frappe.db.sql(
		"""
		select territory,
			   sum(platform_commission_amount) - sum(referral_commission_amount) as net_profit
		from `tabSales Invoice`
		where {conditions}
		group by territory
		""".format(conditions=" and ".join(profit_conditions)),
		profit_values,
		as_dict=True,
	)
	profit_map = {row.territory: flt(row.net_profit) for row in profit_rows if row.territory}

	data = []
	for row in orders:
		if not row.territory:
			continue
		data.append(
			{
				"territory": row.territory,
				"order_count": row.order_count,
				"gmv": row.gmv,
				"net_profit": profit_map.get(row.territory, 0),
				"open_exceptions": exception_map.get(row.territory, 0),
			}
		)
	data.sort(key=lambda r: flt(r["gmv"]), reverse=True)

	report_summary = [
		{"value": len(data), "label": "Active Territories", "datatype": "Int", "indicator": "Blue"},
		{"value": sum(flt(r["gmv"]) for r in data), "label": "Total GMV", "datatype": "Currency", "indicator": "Purple"},
		{"value": sum(flt(r["net_profit"]) for r in data), "label": "Total Net Profit", "datatype": "Currency", "indicator": "Green"},
		{"value": sum(r["open_exceptions"] for r in data), "label": "Open Exceptions", "datatype": "Int", "indicator": "Red"},
	]
	chart = {
		"data": {
			"labels": [r["territory"] for r in data[:10]],
			"datasets": [{"name": "GMV", "values": [flt(r["gmv"]) for r in data[:10]]}],
		},
		"type": "bar",
		"colors": ["#1B3A5C"],
	}
	return columns, data, None, chart, report_summary
