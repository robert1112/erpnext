from __future__ import unicode_literals

import random, json
import frappe, erpnext
from frappe.utils import flt, now_datetime, cstr, random_string
from frappe.utils.make_random import add_random_children, get_random
from erpnext.demo.domains import data
from frappe import _

def setup(domain):
	complete_setup(domain)
	setup_demo_page()
	setup_fiscal_year()
	setup_holiday_list()
	setup_user()
	setup_employee()

	employees = frappe.get_all('Employee',  fields=['name', 'date_of_joining'])

	# monthly salary
	setup_salary_structure(employees[:5], 0)

	# based on timesheet
	setup_salary_structure(employees[5:], 1)

	setup_leave_allocation()
	setup_user_roles()
	setup_customer()
	setup_supplier()
	setup_warehouse()
	import_json('Address')
	import_json('Contact')
	import_json('Lead')
	setup_currency_exchange()
	#setup_mode_of_payment()
	setup_account_to_expense_type()
	setup_budget()
	setup_pos_profile()

	frappe.db.commit()
	frappe.clear_cache()

def complete_setup(domain='Manufacturing'):
	print "Complete Setup..."
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	if not frappe.get_all('Company', limit=1):
		setup_complete({
			"first_name": "Test",
			"last_name": "User",
			"email": "demo@erpnext.com",
			"company_tagline": 'Awesome Products and Services',
			"password": "demo",
			"fy_start_date": "2015-01-01",
			"fy_end_date": "2015-12-31",
			"bank_account": "National Bank",
			"domain": domain,
			"company_name": data.get(domain).get('company_name'),
			"chart_of_accounts": "Standard",
			"company_abbr": ''.join([d[0] for d in data.get(domain).get('company_name').split()]).upper(),
			"currency": 'USD',
			"timezone": 'America/New_York',
			"country": 'United States',
			"language": "english"
		})

def setup_demo_page():
	# home page should always be "start"
	website_settings = frappe.get_doc("Website Settings", "Website Settings")
	website_settings.home_page = "demo"
	website_settings.save()

def setup_fiscal_year():
	fiscal_year = None
	for year in xrange(2010, now_datetime().year + 1, 1):
		try:
			fiscal_year = frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": cstr(year),
				"year_start_date": "{0}-01-01".format(year),
				"year_end_date": "{0}-12-31".format(year)
			}).insert()
		except frappe.DuplicateEntryError:
			pass

	# set the last fiscal year (current year) as default
	fiscal_year.set_as_default()

def setup_holiday_list():
	"""Setup Holiday List for the current year"""
	year = now_datetime().year
	holiday_list = frappe.get_doc({
		"doctype": "Holiday List",
		"holiday_list_name": str(year),
		"from_date": "{0}-01-01".format(year),
		"to_date": "{0}-12-31".format(year),
	})
	holiday_list.insert()
	holiday_list.weekly_off = "Saturday"
	holiday_list.get_weekly_off_dates()
	holiday_list.weekly_off = "Sunday"
	holiday_list.get_weekly_off_dates()
	holiday_list.save()

	frappe.set_value("Company", erpnext.get_default_company(), "default_holiday_list", holiday_list.name)


def setup_user():
	frappe.db.sql('delete from tabUser where name not in ("Guest", "Administrator")')
	for u in json.loads(open(frappe.get_app_path('erpnext', 'demo', 'data', 'user.json')).read()):
		user = frappe.new_doc("User")
		user.update(u)
		user.flags.no_welcome_mail
		user.new_password = 'demo'
		user.insert()

def setup_employee():
	frappe.db.set_value("HR Settings", None, "emp_created_by", "Naming Series")
	frappe.db.commit()

	for d in frappe.get_all('Salary Component'):
		salary_component = frappe.get_doc('Salary Component', d.name)
		salary_component.append('accounts', dict(
			company=erpnext.get_default_company(),
			default_account=frappe.get_value('Account', dict(account_name=('like', 'Salary%')))
		))
		salary_component.save()

	import_json('Employee')

def setup_salary_structure(employees, salary_slip_based_on_timesheet=0):
	f = frappe.get_doc('Fiscal Year', frappe.defaults.get_global_default('fiscal_year'))

	ss = frappe.new_doc('Salary Structure')
	ss.name = "Sample Salary Structure - " + random_string(5)
	for e in employees:
		ss.append('employees', {
			'employee': e.name,
			'base': random.random() * 10000
		})

	ss.from_date = e.date_of_joining if (e.date_of_joining
		and e.date_of_joining > f.year_start_date) else f.year_start_date
	ss.to_date = f.year_end_date
	ss.salary_slip_based_on_timesheet = salary_slip_based_on_timesheet

	if salary_slip_based_on_timesheet:
		ss.salary_component = 'Basic'
		ss.hour_rate = flt(random.random() * 10, 2)
	else:
		ss.payroll_frequency = 'Monthly'

	ss.payment_account = frappe.get_value('Account',
		{'account_type': 'Cash', 'company': erpnext.get_default_company(),'is_group':0}, "name")

	ss.append('earnings', {
		'salary_component': 'Basic',
		"abbr":'B',
		'formula': 'base*.2',
		'amount_based_on_formula': 1,
		"idx": 1
	})
	ss.append('deductions', {
		'salary_component': 'Income Tax',
		"abbr":'IT',
		'condition': 'base > 10000',
		'formula': 'base*.1',
		"idx": 1
	})
	ss.insert()

	return ss

def setup_user_roles():
	user = frappe.get_doc('User', 'demo@erpnext.com')
	user.add_roles('HR User', 'HR Manager', 'Accounts User', 'Accounts Manager',
		'Stock User', 'Stock Manager', 'Sales User', 'Sales Manager', 'Purchase User',
		'Purchase Manager', 'Projects User', 'Manufacturing User', 'Manufacturing Manager',
		'Support Team', 'Academics User')

	if not frappe.db.get_global('demo_hr_user'):
		user = frappe.get_doc('User', 'CharmaineGaudreau@example.com')
		user.add_roles('HR User', 'HR Manager', 'Accounts User')
		frappe.db.set_global('demo_hr_user', user.name)

	if not frappe.db.get_global('demo_sales_user_1'):
		user = frappe.get_doc('User', 'VakhitaRyzaev@example.com')
		user.add_roles('Sales User')
		frappe.db.set_global('demo_sales_user_1', user.name)

	if not frappe.db.get_global('demo_sales_user_2'):
		user = frappe.get_doc('User', 'GabrielleLoftus@example.com')
		user.add_roles('Sales User', 'Sales Manager', 'Accounts User')
		frappe.db.set_global('demo_sales_user_2', user.name)

	if not frappe.db.get_global('demo_purchase_user'):
		user = frappe.get_doc('User', 'MichalSobczak@example.com')
		user.add_roles('Purchase User', 'Purchase Manager', 'Accounts User', 'Stock User')
		frappe.db.set_global('demo_purchase_user', user.name)

	if not frappe.db.get_global('demo_manufacturing_user'):
		user = frappe.get_doc('User', 'NuranVerkleij@example.com')
		user.add_roles('Manufacturing User', 'Stock User', 'Purchase User', 'Accounts User')
		frappe.db.set_global('demo_manufacturing_user', user.name)

	if not frappe.db.get_global('demo_stock_user'):
		user = frappe.get_doc('User', 'HatsueKashiwagi@example.com')
		user.add_roles('Manufacturing User', 'Stock User', 'Purchase User', 'Accounts User')
		frappe.db.set_global('demo_stock_user', user.name)

	if not frappe.db.get_global('demo_accounts_user'):
		user = frappe.get_doc('User', 'LeonAbdulov@example.com')
		user.add_roles('Accounts User', 'Accounts Manager', 'Sales User', 'Purchase User')
		frappe.db.set_global('demo_accounts_user', user.name)

	if not frappe.db.get_global('demo_projects_user'):
		user = frappe.get_doc('User', 'panca@example.com')
		user.add_roles('HR User', 'Projects User')
		frappe.db.set_global('demo_projects_user', user.name)

	if not frappe.db.get_global('demo_schools_user'):
		user = frappe.get_doc('User', 'aromn@example.com')
		user.add_roles('Academics User')
		frappe.db.set_global('demo_schools_user', user.name)

	#Add Expense Approver
	user = frappe.get_doc('User', 'WanMai@example.com')
	user.add_roles('Expense Approver')

def setup_leave_allocation():
	year = now_datetime().year
	for employee in frappe.get_all('Employee', fields=['name']):
		leave_types = frappe.get_all("Leave Type", fields=['name', 'max_days_allowed'])
		for leave_type in leave_types:
			if not leave_type.max_days_allowed:
				leave_type.max_days_allowed = 10

		leave_allocation = frappe.get_doc({
			"doctype": "Leave Allocation",
			"employee": employee.name,
			"from_date": "{0}-01-01".format(year),
			"to_date": "{0}-12-31".format(year),
			"leave_type": leave_type.name,
			"new_leaves_allocated": random.randint(1, int(leave_type.max_days_allowed))
		})
		leave_allocation.insert()
		leave_allocation.submit()
		frappe.db.commit()

def setup_customer():
	customers = [u'Asian Junction', u'Life Plan Counselling', u'Two Pesos', u'Mr Fables', u'Intelacard', u'Big D Supermarkets', u'Adaptas', u'Nelson Brothers', u'Landskip Yard Care', u'Buttrey Food & Drug', u'Fayva', u'Asian Fusion', u'Crafts Canada', u'Consumers and Consumers Express', u'Netobill', u'Choices', u'Chi-Chis', u'Red Food', u'Endicott Shoes', u'Hind Enterprises']
	for c in customers:
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": c,
			"customer_group": "Commercial",
			"customer_type": random.choice(["Company", "Individual"]),
			"territory": "Rest Of The World"
		}).insert()

def setup_supplier():
	suppliers = [u'Helios Air', u'Ks Merchandise', u'HomeBase', u'Scott Ties', u'Reliable Investments', u'Nan Duskin', u'Rainbow Records', u'New World Realty', u'Asiatic Solutions', u'Eagle Hardware', u'Modern Electricals']
	for s in suppliers:
		frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": s,
			"supplier_type": random.choice(["Services", "Raw Material"]),
		}).insert()

def setup_warehouse():
	w = frappe.new_doc('Warehouse')
	w.warehouse_name = 'Supplier'
	w.insert()

def setup_currency_exchange():
	frappe.get_doc({
		'doctype': 'Currency Exchange',
		'from_currency': 'EUR',
		'to_currency': 'USD',
		'exchange_rate': 1.13
	}).insert()

	frappe.get_doc({
		'doctype': 'Currency Exchange',
		'from_currency': 'CNY',
		'to_currency': 'USD',
		'exchange_rate': 0.16
	}).insert()

def setup_mode_of_payment():
	company_abbr = frappe.db.get_value("Company", erpnext.get_default_company(), "abbr")
	account_dict = {'Cash': 'Cash - '+ company_abbr , 'Bank': 'National Bank - '+ company_abbr}
	for payment_mode in frappe.get_all('Mode of Payment', fields = ["name", "type"]):
		if payment_mode.type:
			mop = frappe.get_doc('Mode of Payment', payment_mode.name)
			mop.append('accounts', {
				'company': erpnext.get_default_company(),
				'default_account': account_dict.get(payment_mode.type)
			})
			mop.save(ignore_permissions=True)

def setup_account():
	frappe.flags.in_import = True
	data = json.loads(open(frappe.get_app_path('erpnext', 'demo', 'data',
		'account.json')).read())
	for d in data:
		doc = frappe.new_doc('Account')
		doc.update(d)
		doc.parent_account = frappe.db.get_value('Account', {'account_name': doc.parent_account})
		doc.insert()

def setup_account_to_expense_type():
	company_abbr = frappe.db.get_value("Company", erpnext.get_default_company(), "abbr")
	expense_types = [{'name': _('Calls'), "account": "Sales Expenses - "+ company_abbr},
		{'name': _('Food'), "account": "Entertainment Expenses - "+ company_abbr},
		{'name': _('Medical'), "account": "Utility Expenses - "+ company_abbr},
		{'name': _('Others'), "account": "Miscellaneous Expenses - "+ company_abbr},
		{'name': _('Travel'), "account": "Travel Expenses - "+ company_abbr}]

	for expense_type in expense_types:
		doc = frappe.get_doc("Expense Claim Type", expense_type["name"])
		doc.append("accounts", {
			"company" : erpnext.get_default_company(),
			"default_account" : expense_type["account"]
		})
		doc.save(ignore_permissions=True)

def setup_budget():
	fiscal_years = frappe.get_all("Fiscal Year", order_by="year_start_date")[-2:]

	for fy in fiscal_years:
		budget = frappe.new_doc("Budget")
		budget.cost_center = get_random("Cost Center")
		budget.fiscal_year = fy.name
		budget.action_if_annual_budget_exceeded = "Warn"
		expense_ledger_count = frappe.db.count("Account", {"is_group": "0", "root_type": "Expense"})

		add_random_children(budget, "accounts", rows=random.randint(10, expense_ledger_count), randomize = { 			"account": ("Account", {"is_group": "0", "root_type": "Expense"})
		}, unique="account")

		for d in budget.accounts:
			d.budget_amount = random.randint(5, 100) * 10000

		budget.save()
		budget.submit()

def setup_pos_profile():
	company_abbr = frappe.db.get_value("Company", erpnext.get_default_company(), "abbr")
	pos = frappe.new_doc('POS Profile')
	pos.user = frappe.db.get_global('demo_accounts_user')
	pos.naming_series = 'SINV-'
	pos.update_stock = 0
	pos.write_off_account = 'Cost of Goods Sold - '+ company_abbr
	pos.write_off_cost_center = 'Main - '+ company_abbr

	pos.append('payments', {
		'mode_of_payment': frappe.db.get_value('Mode of Payment', {'type': 'Cash'}, 'name'),
		'amount': 0.0
	})

	pos.insert()

def import_json(doctype, submit=False, values=None):
	frappe.flags.in_import = True
	data = json.loads(open(frappe.get_app_path('erpnext', 'demo', 'data',
		frappe.scrub(doctype) + '.json')).read())
	for d in data:
		doc = frappe.new_doc(doctype)
		doc.update(d)
		doc.insert()
		if submit:
			doc.submit()

	frappe.db.commit()


