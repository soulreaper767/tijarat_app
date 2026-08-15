import frappe


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 120},
		{"label": "Registered", "fieldname": "registered", "fieldtype": "Int", "width": 100},
		{"label": "Productive", "fieldname": "productive", "fieldtype": "Int", "width": 100},
		{"label": "Conversion %", "fieldname": "conversion", "fieldtype": "Percent", "width": 120},
	]

	territory_filter = {"territory": filters["territory"]} if filters.get("territory") else {}

	data = []
	for party_type in ("Customer", "Supplier"):
		registered = frappe.db.count(party_type, {"lifecycle_status": "Registered", **territory_filter})
		productive = frappe.db.count(party_type, {"lifecycle_status": "Productive", **territory_filter})
		total = registered + productive
		conversion = round((productive / total) * 100, 1) if total else 0
		data.append(
			{
				"party_type": party_type,
				"registered": registered,
				"productive": productive,
				"conversion": conversion,
			}
		)

	total_registered = sum(r["registered"] for r in data)
	total_productive = sum(r["productive"] for r in data)
	total = total_registered + total_productive
	report_summary = [
		{"value": total_registered, "label": "Registered", "datatype": "Int", "indicator": "Blue"},
		{"value": total_productive, "label": "Productive", "datatype": "Int", "indicator": "Green"},
		{
			"value": round((total_productive / total) * 100, 1) if total else 0,
			"label": "Overall Conversion",
			"datatype": "Percent",
			"indicator": "Orange",
		},
	]
	chart = {
		"data": {
			"labels": [r["party_type"] for r in data],
			"datasets": [
				{"name": "Registered", "values": [r["registered"] for r in data]},
				{"name": "Productive", "values": [r["productive"] for r in data]},
			],
		},
		"type": "bar",
		"colors": ["#9aa5b1", "#2E7D5B"],
	}
	return columns, data, None, chart, report_summary
