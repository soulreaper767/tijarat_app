import frappe
from frappe.utils import flt, nowdate

PLATFORM_COMMISSION_RATE = 0.02  # 2% - illustrative default, adjust per the business model doc's fee tables


def accrue_commission(doc, method=None):
	"""Runs on Sales Invoice submit. Posts a Journal Entry for the platform's
	own commission immediately (Tijarat earns this the moment the sale is
	invoiced). The *referral* commission is computed and stored here too
	(so it's visible on the invoice and feeds the profitability reports
	right away), but its liability isn't booked until payment actually
	arrives - see settle_referral_payable_on_payment - since Tijarat
	shouldn't owe a referrer a share of money it hasn't collected yet."""
	platform_commission = flt(doc.grand_total) * PLATFORM_COMMISSION_RATE
	doc.db_set("platform_commission_amount", platform_commission)

	_post_commission_journal_entry(doc, platform_commission)

	if doc.get("referral_code"):
		_compute_referral_commission(doc)


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


def _compute_referral_commission(doc):
	"""Stores referral_commission_amount on the invoice and bumps the
	Referral Code's usage count - doesn't touch total_commission_earned or
	post any liability, that's settle_referral_payable_on_payment's job
	once money actually arrives."""
	referral = frappe.get_doc("Referral Code", doc.referral_code)
	rate = referral.get_commission_rate()
	if not rate:
		return
	commission_amount = flt(doc.grand_total) * (flt(rate) / 100)
	doc.db_set("referral_commission_amount", commission_amount)
	referral.record_usage()


def settle_referral_payable_on_payment(doc, method=None):
	"""Payment Entry on_submit. The first payment received against an
	invoice that has a referral commission triggers booking the full
	liability - not prorated across whatever partial payments the invoice
	eventually gets, which keeps this simple rather than splitting a
	commission across an unknown number of future installments."""
	if doc.payment_type != "Receive":
		return

	for ref in doc.get("references", []):
		if ref.reference_doctype == "Sales Invoice":
			_settle_invoice_referral_payable(ref.reference_name)


def _settle_invoice_referral_payable(invoice_name):
	si = frappe.db.get_value(
		"Sales Invoice",
		invoice_name,
		["company", "referral_code", "referral_commission_amount", "referral_payable_posted"],
		as_dict=True,
	)
	if not si or not si.referral_code or not flt(si.referral_commission_amount) or si.referral_payable_posted:
		return

	posted = _post_referral_payable_journal_entry(si.company, invoice_name, si.referral_code, flt(si.referral_commission_amount))
	if posted:
		frappe.db.set_value("Sales Invoice", invoice_name, "referral_payable_posted", 1)
		current = frappe.db.get_value("Referral Code", si.referral_code, "total_commission_earned") or 0
		frappe.db.set_value("Referral Code", si.referral_code, "total_commission_earned", flt(current) + flt(si.referral_commission_amount))


def _post_referral_payable_journal_entry(company, invoice_name, referral_code, amount):
	abbr = frappe.db.get_value("Company", company, "abbr")
	expense_account = f"Referral Commission Expense - {abbr}"
	payable_account = f"Referral Commission Payable - {abbr}"
	if not (frappe.db.exists("Account", expense_account) and frappe.db.exists("Account", payable_account)):
		frappe.log_error(
			title="Tijarat: referral payable accounts missing",
			message=(
				f"Sales Invoice {invoice_name}: referral commission liability was not posted "
				f"because '{expense_account}' / '{payable_account}' don't exist for {company}. "
				f"Run the create_referral_payable_accounts patch, or create the accounts by hand."
			),
		)
		return False

	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": company,
			"posting_date": nowdate(),
			"user_remark": (
				f"Referral commission payable for {invoice_name} "
				f"(Referral Code {referral_code}), booked on payment receipt"
			),
			"accounts": [
				{"account": expense_account, "debit_in_account_currency": amount},
				{"account": payable_account, "credit_in_account_currency": amount},
			],
		}
	)
	je.insert(ignore_permissions=True)
	je.submit()
	return True
