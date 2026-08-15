import frappe
from frappe.utils import flt

PERIOD_FORMAT = {
	"Daily": "%Y-%m-%d",
	"Weekly": "%x-W%v",
	"Monthly": "%Y-%m",
}
PERIOD_UNIT = {"Daily": "Day", "Weekly": "Week", "Monthly": "Month"}


def execute(filters=None):
	"""GMV over time, at whatever granularity the viewer wants - the "by time"
	angle, as one flexible report rather than separate daily/weekly/monthly
	ones."""
	filters = filters or {}
	period = filters.get("period") or "Monthly"
	date_format = PERIOD_FORMAT.get(period, "%Y-%m")

	columns = [
		{"label": "Period", "fieldname": "period", "fieldtype": "Data", "width": 120},
		{"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": "GMV", "fieldname": "gmv", "fieldtype": "Currency", "width": 130},
		{"label": "Avg Invoice Value", "fieldname": "avg_value", "fieldtype": "Currency", "width": 140},
	]

	conditions = ["docstatus = 1"]
	values = {"date_format": date_format}
	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("territory"):
		conditions.append("territory = %(territory)s")
		values["territory"] = filters["territory"]

	data = frappe.db.sql(
		"""
		select date_format(posting_date, %(date_format)s) as period,
			   count(*) as invoice_count,
			   sum(grand_total) as gmv
		from `tabSales Invoice`
		where {conditions}
		group by period
		order by min(posting_date) asc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)
	for row in data:
		row["avg_value"] = flt(row.gmv) / row.invoice_count if row.invoice_count else 0

	total_gmv = sum(flt(r.gmv) for r in data)
	peak = max(data, key=lambda r: flt(r.gmv), default=None)
	report_summary = [
		{"value": total_gmv, "label": "Total GMV", "datatype": "Currency", "indicator": "Green"},
		{"value": sum(r.invoice_count for r in data), "label": "Total Invoices", "datatype": "Int", "indicator": "Blue"},
		{
			"value": (total_gmv / len(data)) if data else 0,
			"label": f"Avg GMV / {PERIOD_UNIT.get(period, period)}",
			"datatype": "Currency",
			"indicator": "Orange",
		},
		{"value": peak.period if peak else "-", "label": "Best Period", "datatype": "Data", "indicator": "Purple"},
	]
	chart = {
		"data": {
			"labels": [r.period for r in data],
			"datasets": [{"name": "GMV", "values": [flt(r.gmv) for r in data]}],
		},
		"type": "line",
		"colors": ["#1B3A5C"],
	}
	return columns, data, None, chart, report_summary
