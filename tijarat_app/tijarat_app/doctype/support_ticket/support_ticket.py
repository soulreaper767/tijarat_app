import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

SLA_HOURS = 48


class SupportTicket(Document):
	def before_insert(self):
		self.raised_by = self.raised_by or frappe.session.user
		self.raised_on = self.raised_on or now_datetime()
		self.sla_due_on = add_to_date(self.raised_on, hours=SLA_HOURS)

	def on_update(self):
		if self.workflow_state == "Resolved" and not self.resolved_on:
			self.db_set("resolved_by", frappe.session.user)
			self.db_set("resolved_on", frappe.utils.now_datetime())
