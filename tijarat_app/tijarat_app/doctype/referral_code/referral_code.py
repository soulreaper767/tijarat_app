import frappe
from frappe.model.document import Document


class ReferralCode(Document):
	def get_commission_rate(self):
		if self.commission_rate:
			return self.commission_rate
		if self.referrer_type == "External Affiliate (Sales Partner)" and self.sales_partner:
			return frappe.db.get_value("Sales Partner", self.sales_partner, "commission_rate") or 0
		return 0

	def record_usage(self, commission_amount=0):
		self.db_set("times_used", (self.times_used or 0) + 1)
		if commission_amount:
			self.db_set(
				"total_commission_earned", (self.total_commission_earned or 0) + commission_amount
			)
