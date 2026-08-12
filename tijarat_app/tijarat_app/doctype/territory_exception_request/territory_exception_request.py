import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class TerritoryExceptionRequest(Document):
	def on_update(self):
		# Stamp who made the decision and when, whenever workflow_state
		# changes away from Pending - the Workflow doctype (fixture) drives
		# the actual state transitions and permission checks; this just
		# records the audit trail.
		if self.workflow_state in ("Approved", "Rejected") and not self.approved_by:
			self.db_set("approved_by", frappe.session.user)
			self.db_set("approved_on", now_datetime())
