import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class JourneyPlanVisit(Document):
	pass


@frappe.whitelist()
def check_in(visit_name, latitude=None, longitude=None):
	"""Called by the Field Officer app when a visit starts."""
	visit = frappe.get_doc("Journey Plan Visit", visit_name)
	visit.check_in_time = now_datetime()
	visit.check_in_latitude = latitude
	visit.check_in_longitude = longitude
	visit.status = "Checked In"
	visit.save(ignore_permissions=True)
	return visit.as_dict()


@frappe.whitelist()
def check_out(visit_name, sales_order=None):
	"""Called when the Field Officer finishes the visit. If an order was
	booked during the visit, pass its name to link it automatically."""
	visit = frappe.get_doc("Journey Plan Visit", visit_name)
	visit.check_out_time = now_datetime()
	visit.status = "Completed"
	if sales_order:
		visit.sales_order = sales_order
	visit.save(ignore_permissions=True)
	return visit.as_dict()
