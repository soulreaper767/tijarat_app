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
	data.sort(key=lambda r: r["compliance"], reverse=True)

	total_planned = sum(r["planned"] for r in data)
	total_completed = sum(r["completed"] for r in data)
	total_missed = sum(r["missed"] for r in data)
	report_summary = [
		{"value": total_planned, "label": "Planned Visits", "datatype": "Int", "indicator": "Blue"},
		{"value": total_completed, "label": "Completed", "datatype": "Int", "indicator": "Green"},
		{"value": total_missed, "label": "Missed", "datatype": "Int", "indicator": "Red"},
		{
			"value": round((total_completed / total_planned) * 100, 1) if total_planned else 0,
			"label": "Overall Compliance",
			"datatype": "Percent",
			"indicator": "Orange",
		},
	]
	chart = {
		"data": {
			"labels": [r["sales_person"] for r in data[:10]],
			"datasets": [{"name": "Compliance %", "values": [r["compliance"] for r in data[:10]]}],
		},
		"type": "bar",
		"colors": ["#2C7A94"],
	}
	return columns, data, None, chart, report_summary
