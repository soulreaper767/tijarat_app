import frappe

# Kanban Board isn't one of the doctypes Frappe syncs from a module JSON
# file (unlike Report/Dashboard Chart/Number Card) - it's a plain data
# record, so it has to be created here rather than shipped as a module file.
BOARDS = [
	{
		"name": "Sales Orders by Status",
		"reference_doctype": "Sales Order",
		"field_name": "status",
		"columns": [
			"Draft", "On Hold", "To Deliver and Bill", "To Bill", "To Deliver", "Completed", "Cancelled", "Closed",
		],
	},
	{
		"name": "Support Tickets by State",
		"reference_doctype": "Support Ticket",
		"field_name": "workflow_state",
		"columns": ["Open", "In Progress", "Resolved", "Escalated"],
	},
]


def execute():
	for board in BOARDS:
		if frappe.db.exists("Kanban Board", board["name"]):
			continue
		if not frappe.db.exists("DocType", board["reference_doctype"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": board["name"],
				"reference_doctype": board["reference_doctype"],
				"field_name": board["field_name"],
				"private": 0,
				"columns": [{"column_name": col} for col in board["columns"]],
			}
		)
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
