import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class ItemListing(Document):
	def validate(self):
		self.validate_dates()
		self.set_default_currency()

	def validate_dates(self):
		if self.valid_from and self.valid_upto:
			if getdate(self.valid_from) > getdate(self.valid_upto):
				frappe.throw("Valid From cannot be after Valid Upto")

	def set_default_currency(self):
		if not self.currency:
			self.currency = frappe.db.get_default("currency") or "PKR"

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
