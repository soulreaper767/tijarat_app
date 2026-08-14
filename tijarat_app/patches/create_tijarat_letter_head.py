import frappe

LETTER_HEAD_NAME = "Tijarat"

CONTENT = """<style>
  .tijarat-lh { display:flex; align-items:center; justify-content:space-between;
    padding-bottom:8px; margin-bottom:10px; border-bottom:2px solid #1B3A5C; font-family:Arial,Helvetica,sans-serif; }
  .tijarat-lh-brand { display:flex; align-items:center; gap:10px; }
  .tijarat-lh-logo { height:40px; width:40px; object-fit:contain; }
  .tijarat-lh-title { font-size:19px; font-weight:700; color:#1B3A5C; letter-spacing:0.5px; line-height:1; margin:0; }
  .tijarat-lh-tagline { font-size:8px; font-weight:600; color:#B8862F; text-transform:uppercase; letter-spacing:0.8px; margin-top:3px; }
  .tijarat-lh-contact { text-align:right; font-size:8px; color:#5a5a5a; line-height:1.5; }
</style>
<div class="tijarat-lh">
  <div class="tijarat-lh-brand">
    <img class="tijarat-lh-logo" src="/files/tijarat_logo.png" alt="Tijarat">
    <div>
      <p class="tijarat-lh-title">TIJARAT</p>
      <div class="tijarat-lh-tagline">The Operating System for Modern Distribution</div>
    </div>
  </div>
  <div class="tijarat-lh-contact">
    www.tijaratapp.com<br>
    support@tijaratapp.com
  </div>
</div>"""


def execute():
	"""Seeds the branded Letter Head every Tijarat print format's `{{ letter_head }}`
	renders - a one-time patch (not after_install) since this app is already
	installed on the live site and after_install only runs on a fresh install."""
	if frappe.db.exists("Letter Head", LETTER_HEAD_NAME):
		doc = frappe.get_doc("Letter Head", LETTER_HEAD_NAME)
		doc.content = CONTENT
		doc.source = "HTML"
		doc.disabled = 0
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": LETTER_HEAD_NAME,
				"source": "HTML",
				"content": CONTENT,
				"is_default": 1,
				"disabled": 0,
			}
		)
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
