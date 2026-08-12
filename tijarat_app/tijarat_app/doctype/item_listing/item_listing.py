import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class ItemListing(Document):
	def validate(self):
		self.validate_dates()
		self.set_default_currency()
		self.auto_mark_territory()

	def validate_dates(self):
		if self.valid_from and self.valid_upto:
			if getdate(self.valid_from) > getdate(self.valid_upto):
				frappe.throw("Valid From cannot be after Valid Upto")

	def set_default_currency(self):
		if not self.currency:
			self.currency = frappe.db.get_default("currency") or "PKR"

	def auto_mark_territory(self):
		"""Leaving Territory blank on a new listing defaults it to the
		Supplier's primary served territory rather than "all territories" -
		a supplier who serves more than one territory still gets a sensible
		default here (their home one) and creates additional listings for
		the others, same as any other item they list. Only applies on
		create - never overrides a value someone already chose or is editing."""
		if self.territory or not self.supplier or not self.is_new():
			return

		coverage = frappe.get_all(
			"Territory Coverage",
			filters={"parent": self.supplier, "parenttype": "Supplier"},
			fields=["territory"],
			order_by="is_primary desc",
			limit=1,
		)
		if coverage:
			self.territory = coverage[0].territory

	def is_currently_valid(self):
		"""Used by the marketplace API to filter listings that are active
		and within their date range, if one is set."""
		if not self.is_active:
			return False
		today = getdate(nowdate())
		if self.valid_from and getdate(self.valid_from) > today:
			return False
		if self.valid_upto and getdate(self.valid_upto) < today:
			return False
		return True
