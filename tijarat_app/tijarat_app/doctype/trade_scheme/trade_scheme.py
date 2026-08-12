import frappe
from frappe.model.document import Document


class TradeScheme(Document):
	def validate(self):
		if self.valid_from and self.valid_upto and self.valid_from > self.valid_upto:
			frappe.throw("Valid From cannot be after Valid Upto")

	def on_update(self):
		"""Trade Scheme is not submittable - it's driven by the Trade Scheme
		Approval workflow (workflow_state field). The underlying Pricing Rule
		is only created once, the first time the scheme reaches Published, so
		a manufacturer's discount goes live everywhere it applies without
		anyone hand-building the Pricing Rule."""
		if self.workflow_state == "Published" and not self.pricing_rule:
			self._create_pricing_rule()

	def _create_pricing_rule(self):
		# apply_on = "Item Group" with the root group is the standard ERPNext
		# way to express "applies broadly" - Trade Scheme has no per-item
		# scoping of its own, only territory/customer group.
		rule = frappe.get_doc(
			{
				"doctype": "Pricing Rule",
				"title": f"Trade Scheme: {self.scheme_name}",
				"apply_on": "Item Group",
				"items": [],
				"item_groups": [{"item_group": "All Item Groups"}],
				"price_or_product_discount": "Price",
				"rate_or_discount": "Discount Percentage" if self.discount_type == "Percentage" else "Discount Amount",
				"discount_percentage": self.discount_value if self.discount_type == "Percentage" else 0,
				"discount_amount": self.discount_value if self.discount_type == "Flat Amount" else 0,
				"valid_from": self.valid_from,
				"valid_upto": self.valid_upto,
				"territory": [{"territory": self.applies_to_territory}] if self.applies_to_territory else [],
				"customer_group": [{"customer_group": self.applies_to_customer_group}]
				if self.applies_to_customer_group
				else [],
				"selling": 1,
				"disable": 0 if self.is_active else 1,
			}
		)
		rule.insert(ignore_permissions=True)
		self.db_set("pricing_rule", rule.name)
