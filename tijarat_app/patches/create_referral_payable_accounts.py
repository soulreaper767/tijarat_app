import frappe

# Not tied to a specific Party (Sales Person/Sales Partner aren't in ERPNext's
# native party-accounting allowlist for Journal Entry, so party-linking these
# would risk a validation error) - who each posting is owed to is tracked via
# the Journal Entry's own user_remark instead, cross-referenced against the
# Referral Code doctype's running totals.
ACCOUNTS = [
	{"name": "Referral Commission Payable", "type": "Payable", "based_on": "default_payable_account"},
	{"name": "Referral Commission Expense", "type": "Expense Account", "based_on": "default_expense_account"},
]


def execute():
	for company in frappe.get_all("Company", pluck="name"):
		for account in ACCOUNTS:
			_ensure_account(company, account["name"], account["type"], account["based_on"])
	frappe.db.commit()


def _ensure_account(company, account_name, account_type, based_on_field):
	abbr = frappe.db.get_value("Company", company, "abbr")
	full_name = f"{account_name} - {abbr}"
	if frappe.db.exists("Account", full_name):
		return

	reference_account = frappe.db.get_value("Company", company, based_on_field)
	parent = frappe.db.get_value("Account", reference_account, "parent_account") if reference_account else None
	if not parent:
		frappe.log_error(
			title="Tijarat: could not create referral payable account",
			message=(
				f"Company {company} has no {based_on_field} configured (or it has no parent "
				f"group), so '{account_name}' could not be created automatically. Set up "
				f"Company Accounting Settings and re-run this patch, or create the account by hand."
			),
		)
		return

	frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": company,
			"parent_account": parent,
			"is_group": 0,
			"account_type": account_type,
		}
	).insert(ignore_permissions=True)
