import frappe


def execute(filters=None):
	filters = filters or {}
	columns = [
		{
			"label": "Field Officer",
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 160,
		},
		{"label": "Planned", "fieldname": "planned", "fieldtype": "Int", "width": 90},
		{"label": "Completed", "fieldname": "completed", "fieldtype": "Int", "width": 90},
		{"label": "Missed", "fieldname": "missed", "fieldtype": "Int", "width": 90},
		{"label": "Compliance %", "fieldname": "compliance", "fieldtype": "Percent", "width": 120},
	]

	conditions = ["1=1"]
	values = {}
	if filters.get("from_date"):
		conditions.append("visit_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("visit_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("sales_person"):
		conditions.append("sales_person = %(sales_person)s")
		values["sales_person"] = filters["sales_person"]

	rows = frappe.db.sql(
		"""
		select sales_person,
			   sum(case when status in ('Completed','Checked In') then 1 else 0 end) as completed,
			   sum(case when status = 'Missed' then 1 else 0 end) as missed,
			   count(*) as planned
		from `tabJourney Plan Visit`
		where {conditions}
		group by sales_person
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	data = []
	for row in rows:
		row["compliance"] = round((row.completed / row.planned) * 100, 1) if row.planned else 0
		data.append(row)
	return columns, data
