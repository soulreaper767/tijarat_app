// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Referral & Affiliate Commission"] = {
	filters: [
		{
			fieldname: "referrer_type",
			label: __("Referrer Type"),
			fieldtype: "Select",
			options: "\nField Officer (Sales Person)\nExternal Affiliate (Sales Partner)",
		},
	],
};
