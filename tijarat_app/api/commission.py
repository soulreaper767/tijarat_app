import frappe
from frappe.utils import flt

PLATFORM_COMMISSION_RATE = 0.02  # 2% - illustrative default, adjust per the business model doc's fee tables


def accrue_commission(doc, method=None):
	"""Runs on Sales Invoice submit. Posts a Journal Entry for the platform's
	own commission, and separately updates the Referral Code's running
	total if this sale came from one - referral/affiliate commission is
	tracked via native Sales Partner/Sales Person commission fields, this
	function only handles the platform-side accrual and the Referral Code's
	own reporting counters."""
	platform_commission = flt(doc.grand_total) * PLATFORM_COMMISSION_RATE
	doc.db_set("platform_commission_amount", platform_commission)

	_post_commission_journal_entry(doc, platform_commission)

	if doc.get("referral_code"):
		_accrue_referral_commission(doc)


def _post_commission_journal_entry(doc, amount):
	if not amount:
		return

	income_account = frappe.db.get_value("Company", doc.company, "default_income_account")
	receivable_account = frappe.db.get_value("Company", doc.company, "default_receivable_account")
	if not (income_account and receivable_account):
		frappe.log_error(
			title="Tijarat commission accrual skipped",
			message=f"Sales Invoice {doc.name}: Company {doc.company} is missing a default "
			f"income or receivable account, so the platform commission Journal Entry was not posted.",
		)
		return

	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": doc.company,
			"posting_date": doc.posting_date,
			"user_remark": f"Platform commission accrual for {doc.name}",
			"accounts": [
				{"account": receivable_account, "debit_in_account_currency": amount, "party_type": "Customer", "party": doc.customer},
				{"account": income_account, "credit_in_account_currency": amount},
			],
		}
	)
	je.insert(ignore_permissions=True)
	je.submit()


def _accrue_referral_commission(doc):
	referral = frappe.get_doc("Referral Code", doc.referral_code)
	rate = referral.get_commission_rate()
	if not rate:
		return
	commission_amount = flt(doc.grand_total) * (flt(rate) / 100)
	doc.db_set("referral_commission_amount", commission_amount)
	referral.record_usage(commission_amount)
