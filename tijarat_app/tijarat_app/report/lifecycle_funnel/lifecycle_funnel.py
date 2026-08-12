import frappe


def execute(filters=None):
	columns = [
		{"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 120},
		{"label": "Registered", "fieldname": "registered", "fieldtype": "Int", "width": 100},
		{"label": "Productive", "fieldname": "productive", "fieldtype": "Int", "width": 100},
		{"label": "Conversion %", "fieldname": "conversion", "fieldtype": "Percent", "width": 120},
	]

	data = []
	for party_type in ("Customer", "Supplier"):
		registered = frappe.db.count(party_type, {"lifecycle_status": "Registered"})
		productive = frappe.db.count(party_type, {"lifecycle_status": "Productive"})
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
	return columns, data
