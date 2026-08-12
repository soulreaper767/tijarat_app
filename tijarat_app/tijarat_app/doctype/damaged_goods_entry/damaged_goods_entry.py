import frappe
from frappe.model.document import Document


class DamagedGoodsEntry(Document):
	def before_insert(self):
		self.reported_by = self.reported_by or frappe.session.user
