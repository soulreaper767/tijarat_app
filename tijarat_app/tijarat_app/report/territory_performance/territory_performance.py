import frappe


def execute(filters=None):
	columns = [
		{"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150},
		{"label": "Orders", "fieldname": "order_count", "fieldtype": "Int", "width": 90},
		{"label": "GMV", "fieldname": "gmv", "fieldtype": "Currency", "width": 130},
		{"label": "Open Territory Exceptions", "fieldname": "open_exceptions", "fieldtype": "Int", "width": 170},
	]

	orders = frappe.db.sql(
		"""
		select c.territory as territory, count(*) as order_count, sum(so.grand_total) as gmv
		from `tabSales Order` so
		join `tabCustomer` c on c.name = so.customer
		where so.docstatus = 1
		group by c.territory
		""",
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

	data = []
	for row in orders:
		if not row.territory:
			continue
		data.append(
			{
				"territory": row.territory,
				"order_count": row.order_count,
				"gmv": row.gmv,
				"open_exceptions": exception_map.get(row.territory, 0),
			}
		)
	return columns, data
