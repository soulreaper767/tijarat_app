import frappe

DEFAULT_RECIPIENT = "hello@tijaratapp.com"

AUTO_EMAIL_REPORTS = [
	{"report": "GMV & Commission Summary", "frequency": "Daily"},
	{"report": "Territory Performance", "frequency": "Weekly", "day_of_week": "Monday"},
	{"report": "Top Customers", "frequency": "Weekly", "day_of_week": "Monday"},
	{"report": "Party-Wise Profitability", "frequency": "Monthly"},
	{"report": "Referral & Affiliate Commission", "frequency": "Monthly"},
	{"report": "Courier Performance", "frequency": "Weekly", "day_of_week": "Monday"},
]


def execute():
	for config in AUTO_EMAIL_REPORTS:
		_ensure_auto_email_report(config)
	frappe.db.commit()


def _ensure_auto_email_report(config):
	if frappe.db.exists(
		"Auto Email Report", {"report": config["report"], "frequency": config["frequency"]}
	):
		return
	try:
		doc = frappe.new_doc("Auto Email Report")
		doc.report = config["report"]
		doc.user = "Administrator"
		doc.enabled = 1
		doc.format = "XLSX"
		doc.frequency = config["frequency"]
		doc.email_to = DEFAULT_RECIPIENT
		if config.get("day_of_week"):
			doc.day_of_week = config["day_of_week"]
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Tijarat: could not create auto email report",
			message=(
				f"Auto Email Report for '{config['report']}' ({config['frequency']}) could not be "
				f"created: {frappe.get_traceback()}"
			),
		)
