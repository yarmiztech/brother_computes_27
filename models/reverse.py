# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from datetime import date
from datetime import datetime
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import calendar
import re
import json
from dateutil.relativedelta import relativedelta
import pgeocode
import qrcode
from PIL import Image
from random import choice
from string import digits
import json
import re
import uuid
from functools import partial


class Pdccheque(models.Model):
    _inherit = "pdc.cheque.collection"

    def _compute_status_compute(self):
        for each in self:
            if len(each.partner_invoices.filtered(lambda a: a.state == 'deposit')) > 0:
                each.status_compute = True
            else:
                each.status_compute = False



class CreditLimitRecord(models.Model):
    _inherit = "credit.limit.record"


    @api.onchange('date')
    def onchange_date(self):
        if self.date:
            months = self.env['credit.limit.configuration'].search([('active', '=', True)]).months
            percentage = self.env['credit.limit.configuration'].search([('active', '=', True)]).percentage
            min_credit_amt = self.env['credit.limit.configuration'].search([('active', '=', True)]).min_credit_amount
            from_month = datetime.today().date() - relativedelta(months=months)
            to_month = datetime.today().date()
            list = []

            for partner_wise in self.env['partner.ledger.customer'].search(
                    [('company_id', '=', 1), ('date', '>=', from_month), ('date', '<=', to_month),
                     ('debit', '!=', 0)]).filtered(lambda a: a.debit >= 1).mapped('partner_id'):
                avg_amt = 0
                for each in sorted(self.env['partner.ledger.customer'].search(
                        [('company_id', '=', 1), ('date', '>=', from_month), ('date', '<=', to_month),
                         ('partner_id', '=', partner_wise.id)])):
                    avg_amt += each.debit
                    balance = each.balance
                value = percentage / 100
                aveg_amount = avg_amt / months
                basic_value = aveg_amount * value
                print(partner_wise, 'partner_wise')
                credit_amount = 0
                if min_credit_amt > basic_value:
                    credit_amount = min_credit_amt
                else:
                    credit_amount = basic_value

                line = (0, 0, {
                    'partner_id': each.partner_id.id,
                    'balance': balance,
                    'average_amount': aveg_amount,
                    'credit_limit_amount': basic_value,
                    'min_credit_amount': credit_amount
                })
                list.append(line)
            self.credit_limit_lines = list


class DataEntryLine(models.Model):
    _inherit = "data.entry.line"

    vehicle_id = fields.Many2one('fleet.vehicle',string="Vehicle Id")



class AreaCustomersOther(models.Model):
    _inherit = 'areas.customers.other'

    @api.depends('collected_amount')
    def _compute_balance(self):
        for line in self:
            line.balance =0.0
            if line.out_standing_balance:
                line.balance = line.out_standing_balance - line.collected_amount

class AreaCustomersFilter(models.Model):
    _inherit = 'areas.filter.lines'

    @api.depends('collected_amount')
    def _compute_balance(self):
        for line in self:
            line.balance =0.0
            if line.out_standing_balance:
                line.balance = line.out_standing_balance - line.collected_amount


class ExecutiveFullReport(models.Model):
    _inherit = "executive.full.report"


    @api.onchange('sales_person', 'from_date', 'to_date', 'type')
    def onchange_from_date(self):
        self.executive_lines = False
        today_total_cheques = []
        if self.type == 'total':
            self.executive_lines = False
            self.collected_lines = False
            self.visited_lines = False
            if not self.sales_person:
                for each_cheque in self.env['sales.person.details'].search(
                        [('company_id', '=', self.company_id.id), ('create_date', '>=', self.from_date),
                         ('create_date', '<=', self.to_date)]):
                    # for each_target in each_cheque.target_lines:
                    product_line = (0, 0, {
                        'create_date': each_cheque.create_date,
                        'sales_person': each_cheque.sales_person.id,
                        'partner_id': each_cheque.partner_id.id,
                        'product_id': each_cheque.product_id.id,
                        'product_uom_qty': each_cheque.product_uom_qty,
                        'price': each_cheque.price,
                        'subtotal': each_cheque.subtotal,
                    })
                    today_total_cheques.append(product_line)
            else:
                for each_cheque in self.env['sales.person.details'].search(
                        [('sales_person','=',self.sales_person.id),('company_id', '=', self.company_id.id), ('create_date', '>=', self.from_date),
                         ('create_date', '<=', self.to_date)]):
                    # for each_target in each_cheque.target_lines:
                    product_line = (0, 0, {
                        'create_date': each_cheque.create_date,
                        'sales_person': each_cheque.sales_person.id,
                        'partner_id': each_cheque.partner_id.id,
                        'product_id': each_cheque.product_id.id,
                        'product_uom_qty': each_cheque.product_uom_qty,
                        'price': each_cheque.price,
                        'subtotal': each_cheque.subtotal,
                    })
                    today_total_cheques.append(product_line)
            self.executive_lines = today_total_cheques

        if self.type == 'collected':
            self.executive_lines = False
            self.collected_lines = False
            self.visited_lines = False
            for each_cheque in self.env['executive.collection'].search(
                    [('payment_date', '>=', self.from_date),
                     ('payment_date', '<=', self.to_date)]):
                for each_target in each_cheque.partner_invoices:
                    product_line = (0, 0, {
                        'date': each_cheque.payment_date,
                        'sales_person': each_cheque.user_id.partner_id.id,
                        'partner_id': each_target.partner_id.id,
                        'type': 'Cash',
                        'outstanding_balance': each_target.balance_amount,
                        'collected_amount': each_target.amount_total,
                        'balance': each_target.balance_amount - each_target.amount_total,
                    })
                    today_total_cheques.append(product_line)

            for each_cheque in self.env['executive.cheque.collection'].search(
                    [('payment_date', '>=', self.from_date),
                     ('payment_date', '<=', self.to_date)]):
                for each_target in each_cheque.partner_invoices:
                    product_line = (0, 0, {
                        'date': each_cheque.payment_date,
                        'sales_person': each_cheque.user_id.partner_id.id,
                        'partner_id': each_target.partner_id.id,
                        'outstanding_balance': each_target.balance_amount,
                        'collected_amount': each_target.amount_total,
                        'type':'Cheque',
                        'balance': each_target.balance_amount - each_target.amount_total,
                    })
                    today_total_cheques.append(product_line)

            self.collected_lines = today_total_cheques
        if self.type == 'visit':
            self.executive_lines = False
            self.collected_lines = False
            self.visited_lines = False
            for each_cheque in self.env['executive.areas.assign'].sudo().search(
                    [('sales_person','=',self.sales_person.id),('company_id', '=', self.company_id.id), ('date', '>=', self.from_date),
                     ('date', '<=', self.to_date)]):
                for each_target in each_cheque.partner_lines:
                    product_line = (0, 0, {
                        'date': each_cheque.date,
                        'sales_person': each_cheque.sales_person.id,
                        'partner_id': each_target.partner_id.id,
                        'reason': each_target.reason,
                        'state': each_target.state,
                        'next_visit_date': each_target.next_visit_date,
                    })
                    today_total_cheques.append(product_line)
                for each_target in each_cheque.partner_other_lines:
                    product_line = (0, 0, {
                        'date': each_cheque.date,
                        'sales_person': each_cheque.sales_person.id,
                        'partner_id': each_target.partner_id.id,
                        'reason': each_target.reason,
                        'state': each_target.state,
                        'next_visit_date': each_target.next_visit_date,
                    })
                    today_total_cheques.append(product_line)

            self.visited_lines = today_total_cheques


class BulkCollections(models.Model):
    _inherit = "bulk.collections"


    def action_confirm(self):
        if self.collection_type == "cash":
            for line in self.bulk_lines:
                if line.amount_total == 0.0:
                    raise UserError(_("Please mention paid amount for this partner %s ")%(line.partner_id.name))
                cv = 0
                # if line.check_type == 'cheque':
                #     journal = self.env['account.journal'].search(
                #         [('name', '=', 'Bank'), ('company_id', '=', self.env.user.company_id.id)])
                # else:
                journal = line.journal_id.id
                stmt = self.env['account.bank.statement']
                if not stmt:
                    # _get_payment_info_JSON
                    # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.journal_id.id)]).mapped(
                    #     'debit'))

                    if self.env['account.bank.statement'].search([('company_id', '=', line.journal_id.company_id.id),
                                                                  ('journal_id', '=', line.journal_id.id)]):
                        bal = self.env['account.bank.statement'].search(
                            [('company_id', '=', line.journal_id.company_id.id),
                             ('journal_id', '=', line.journal_id.id)])[0].balance_end_real
                    else:
                        bal = 0




                    stmt = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                      'balance_start': bal,
                                                                      # 'journal_id': line.journal_id.id,
                                                                      'journal_id': line.journal_id.id,
                                                                      # 'balance_end_real': line.amount_total
                                                                      'balance_end_real': bal+line.amount_total

                                                                      })

                payment_list = []
                pay_id_list = []
                account = self.env['account.move'].search([('partner_id','=',line.partner_id.id),('state','=','posted')])
                amount = line.amount_total
                actual =0
                for check_inv in account:
                    if amount:
                        if check_inv.amount_total >= amount:
                            actual=amount
                            product_line = (0, 0, {
                                'date': line.payment_date,
                                'name': check_inv.display_name,
                                'partner_id': line.partner_id.id,
                                'payment_ref': check_inv.display_name,
                                'amount': amount
                            })
                            amount = amount - amount
                            payment_list.append(product_line)
                        else:
                            if check_inv.amount_total != 0:
                                amount = amount-check_inv.amount_total
                                actual =check_inv.amount_total
                                product_line = (0, 0, {
                                    'date': self.payment_date,
                                    'name': check_inv.display_name,
                                    'partner_id': line.partner_id.id,
                                    'payment_ref': check_inv.display_name,
                                    'amount': check_inv.amount_total
                                })
                                payment_list.append(product_line)

                        j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]

                        pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                     # 'amount': check_inv.amount_total,
                                                                     'amount': actual,
                                                                     'partner_type': 'customer',
                                                                     'company_id': self.env.user.company_id.id,
                                                                     'payment_type': 'inbound',
                                                                     'payment_method_id': j.id,
                                                                     # 'journal_id': line.journal_id.id,
                                                                     'journal_id': line.journal_id.id,
                                                                     'ref': 'Cash Collection',
                                                                     # 'invoice_ids': [(6, 0, check_inv.ids)]
                                                                     # 'move_id': check_inv.id
                                                                     })
                        # pay_id.action_validate_invoice_payment()
                        pay_id.action_post()
                        # for k in pay_id.move_line_ids:
                        for k in pay_id.line_ids:
                            pay_id_list.append(k.id)
                        # line.payments += pay_id
                        executive_rec = self.env['executive.collection.record'].search(
                            [('collection_line_id', '=', line.collection_line.id)])
                        # executive_rec.amount_total += line.amount_total
                        executive_rec.status =True


            if stmt:
                stmt.line_ids = payment_list
                stmt.move_line_ids = pay_id_list
                # stmt.write({'state': 'confirm'})
                # self.write({'state': 'validate'})

        if self.collection_type == "cheque":
            for line in self.bulk_cheque_lines:
                stmt = self.env['account.bank.statement']
                if self.env['account.move'].search([('company_id','=',self.env.user.company_id.id),('partner_id','=',line.partner_id.id)]):
                    if line.amount_total == 0.0:
                        raise UserError(_("Please mention paid amount for this partner %s ")%(line.partner_id.name))
                    cv = 0
                    # if line.check_type == 'cheque':
                    #     journal = self.env['account.journal'].search(
                    #         [('name', '=', 'Bank'), ('company_id', '=', self.env.user.company_id.id)])
                    # else:
                    # journal = line.journal_id.id
                    journal = self.env['account.journal'].search([('name','=','Bank'),('company_id','=',1)])
                    # journal = self.env['account.journal'].search([('name','=','SHIHAB'),('company_id','=',1)])
                    if not stmt:
                        # _get_payment_info_JSON
                        # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.debited_account.id)]).mapped(
                        #     'debit'))

                        if self.env['account.bank.statement'].search([('company_id', '=', journal.company_id.id),
                                                                      ('journal_id', '=', journal.id)]):
                            bal = self.env['account.bank.statement'].search(
                                [('company_id', '=', journal.company_id.id),
                                 ('journal_id', '=', journal.id)])[0].balance_end_real
                        else:
                            bal = 0


                        stmt = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                          'balance_start': bal,
                                                                          # 'journal_id': line.journal_id.id,
                                                                          'journal_id': journal.id,
                                                                          'balance_end_real': bal+line.amount_total

                                                                          })

                    payment_list = []
                    pay_id_list = []
                    account = self.env['account.move']
                    check_inv = self.env['account.move']
                    account = self.env['account.move'].search([('company_id','=',self.env.user.company_id.id),('move_type','=','out_invoice'),('amount_residual','!=',0),('partner_id','=',line.partner_id.id),('state','=','posted')])
                    amount = line.amount_total
                    actual =0
                    if account:
                        for check_inv in account:
                            if amount:
                                if check_inv.amount_residual >= amount:
                                    # sub_c_invoice = check_inv.estimate_id.invoice_ids.filtered(lambda a: a.company_id.id != 1)
                                    sub_c_invoice = check_inv.estimate_id.invoice_ids.filtered(lambda a: a.company_id.id == line.debited_account.company_id.id)
                                    if not sub_c_invoice:
                                        continue
                                    actual=amount
                                    if sub_c_invoice:
                                        self.sub_company_payment(sub_c_invoice,line,amount)
                                    else:
                                        self.advance_sub_company_payment(sub_c_invoice, line, amount)
                                    product_line = (0, 0, {
                                        'date': line.date,
                                        'name': check_inv.display_name,
                                        'partner_id': line.partner_id.id,
                                        'payment_ref': check_inv.display_name,
                                        'amount': amount
                                    })
                                    amount = amount - amount
                                    payment_list.append(product_line)
                                else:
                                    if check_inv.amount_residual != 0:
                                        sub_c_invoice = check_inv.estimate_id.invoice_ids.filtered(
                                            lambda a: a.company_id.id == line.debited_account.company_id.id)
                                        if not sub_c_invoice:
                                            continue
                                        self.sub_company_payment(sub_c_invoice, line,amount)
                                        amount = amount-check_inv.amount_residual
                                        actual = check_inv.amount_residual
                                        product_line = (0, 0, {
                                            'date': line.date,
                                            'name': check_inv.display_name,
                                            'partner_id': line.partner_id.id,
                                            'payment_ref': check_inv.display_name,
                                            'amount': check_inv.amount_residual
                                        })
                                        payment_list.append(product_line)

                                j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                                # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                                # pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                #                                              # 'amount': check_inv.amount_residual,
                                #                                              'amount': actual,
                                #                                              'partner_type': 'customer',
                                #                                              'company_id': self.env.user.company_id.id,
                                #                                              'payment_type': 'inbound',
                                #                                              'payment_method_id': j.id,
                                #                                              # 'journal_id': line.journal_id.id,
                                #                                              'journal_id': journal.id,
                                #                                              'ref': line.check_no+'=>'+'Cleared',
                                #                                              # 'invoice_ids': [(6, 0, check_inv.ids)]
                                #                                              # 'move_id': check_inv.id
                                #                                              })
                                # pay_id.action_validate_invoice_payment()
                                # pay_id.action_post()

                                # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                                pmt_wizard = self.env['account.payment.register'].with_context(
                                    active_model='account.move',
                                    active_ids=check_inv.ids).create(
                                    {
                                        'payment_date': check_inv.date,
                                        'journal_id': journal.id,
                                        'payment_method_id': self.env.ref(
                                            'account.account_payment_method_manual_in').id,
                                        'amount': actual,

                                    })
                                pmt_wizard._create_payments()

                                invoices = self.env['account.move'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', self.env.user.company_id.id),('state', '!=', 'paid')])
                                if invoices.mapped('amount_residual'):
                                    balance_amount = sum(invoices.mapped('amount_residual'))
                                else:
                                    balance_amount = sum(invoices.mapped('amount_total'))
                                balance_amount += self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('description', '=', 'Opening Balance')]).balance
                                balance_amount_ref = self.env['partner.ledger.customer'].search([('company_id','=',self.env.user.company_id.id),('partner_id', '=', line.partner_id.id)])
                                if balance_amount_ref:
                                   balance_amount = self.env['partner.ledger.customer'].search([('company_id','=',self.env.user.company_id.id),('partner_id', '=', line.partner_id.id)])[-1].balance


                                for m in check_inv:
                                    led = self.env['partner.ledger.customer'].search(
                                        [('partner_id', '=', m.partner_id.id),
                                         ('company_id', '=', m.company_id.id),('invoice_id','=',m.id)])
                                    leds = self.env['partner.ledgers.customer'].search(
                                        [('partner_id', '=', m.partner_id.id),
                                         ('company_id', '=', m.company_id.id),('invoice_id','=',m.id)])

                                    for l in led:
                                        # l.description = line.check_no + '=>' + 'Cleared',
                                        # l.credit += actual
                                        # l.balance = balance_amount-actual
                                        # l.account_journal = journal.id
                                        # l.account = journal.default_debit_account_id.id
                                        # l.paid_date = datetime.today().date()
                                        # l.account_move = pay_id.move_line_ids.mapped('move_id')[0].id
                                        self.env['partner.ledger.customer'].sudo().create({
                                            'date': datetime.today().date(),
                                            'partner_id': line.partner_id.id,
                                            'company_id': m.company_id.id,
                                            'credit': actual,
                                            'check_only': True,
                                            # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                            'account_move': m.id,
                                            'balance': balance_amount - actual,
                                            'description': line.check_no + '=>' + 'Cleared Amount',
                                            'account_journal': journal.id,
                                            'account': journal.payment_debit_account_id.id,
                                            'paid_date': datetime.today().date()

                                        })

                                    for ls in leds:
                                        ls.description = line.check_no + '=>' + 'Cleared',
                                        ls.credit += actual
                                        ls.account_journal = journal.id
                                        ls.account = journal.payment_debit_account_id.id
                                        ls.paid_date = datetime.today().date()

                                # for k in pay_id.move_line_ids:
                                # for k in pay_id.line_ids:
                                #     pay_id_list.append(k.id)
                                # line.payments += pay_id
                                executive_rec = self.env['collection.cheque'].search([('check_line','=',line.check_line.id)])
                                # executive_rec.amount_total += line.amount_total
                                executive_rec.al_state =True
                    else:
                        j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                        if actual:
                            pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                         # 'amount': check_inv.amount_total,
                                                                         'amount': actual,
                                                                         'partner_type': 'customer',
                                                                         'company_id': self.env.user.company_id.id,
                                                                         'payment_type': 'inbound',
                                                                         'payment_method_id': j.id,
                                                                         # 'journal_id': line.journal_id.id,
                                                                         'journal_id': journal.id,
                                                                         'ref': line.check_no,

                                                                         })
                            # pay_id.post()
                            pay_id.action_post()
                            pay_id.action_cash_book()
                            invoices = self.env['account.move'].search(
                                [('partner_id', '=', line.partner_id.id),
                                 ('company_id', '=', self.env.user.company_id.id),('state', '!=', 'paid')])
                            if invoices.mapped('amount_residual'):
                                balance_amount = sum(invoices.mapped('amount_residual'))
                            else:
                                balance_amount = sum(invoices.mapped('amount_total'))
                            balance_amount += self.env['partner.ledger.customer'].search(
                                [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                            balance_amount = self.env['partner.ledger.customer'].search(
                                [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])[-1].balance
                            if check_inv:
                                for m in check_inv:
                                    led = self.env['partner.ledger.customer'].search(
                                        [('partner_id', '=', m.partner_id.id),
                                         ('company_id', '=', m.company_id.id)])
                                    leds = self.env['partner.ledgers.customer'].search(
                                        [('partner_id', '=', m.partner_id.id),
                                         ('company_id', '=', m.company_id.id)])
                                    for l in led:
                                        # l.description = line.check_no + '=>' + 'Cleared',
                                        # l.credit += actual
                                        # l.balance = balance_amount-actual
                                        # l.account_journal = journal.id
                                        # l.account = journal.default_debit_account_id.id
                                        # l.paid_date = datetime.today().date()
                                        self.env['partner.ledger.customer'].sudo().create({
                                            'date': datetime.today().date(),
                                            'partner_id': line.partner_id.id,
                                            'company_id': m.company_id.id,
                                            'credit': actual,
                                            'check_only': True,
                                            # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                            'account_move': pay_id.move_id.id,
                                            'balance': balance_amount-actual,
                                            'description': line.check_no + '=>' + 'Cleared Amount',
                                            'account_journal': journal.id,
                                            'account': journal.payment_debit_account_id.id,
                                            'paid_date': datetime.today().date()

                                        })


                                    for ls in leds:
                                        ls.description = line.check_no + '=>' + 'Cleared',
                                        ls.credit += actual
                                        ls.account_journal = journal.id
                                        ls.account = journal.payment_debit_account_id.id
                                        ls.paid_date = datetime.today().date()
                        else:
                            # for m in check_inv:
                                balance_amount = 0
                                balance_amount += self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                                if self.env['partner.ledger.customer'].search(
                                    [('company_id', '=', self.env.user.company_id.id),
                                     ('partner_id', '=', line.partner_id.id)]):
                                        balance_amount = self.env['partner.ledger.customer'].search(
                                                        [('company_id', '=', self.env.user.company_id.id),
                                                         ('partner_id', '=', line.partner_id.id)])[-1].balance
                                led = self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', line.debited_account.company_id.id)])
                                leds = self.env['partner.ledgers.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', line.debited_account.company_id.id)])
                                for l in led:
                                    # l.description = line.check_no + '=>' + 'Cleared',
                                    # l.credit += actual
                                    # l.balance = balance_amount-actual
                                    # l.account_journal = journal.id
                                    # l.account = journal.default_debit_account_id.id
                                    # l.paid_date = datetime.today().date()
                                    self.env['partner.ledger.customer'].sudo().create({
                                        'date': datetime.today().date(),
                                        'partner_id': line.partner_id.id,
                                        'company_id': line.debited_account.company_id.id,
                                        'credit': actual,
                                        'check_only': True,
                                        # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                        'balance': balance_amount-actual,
                                        'description': line.check_no + '=>' + 'Cleared Amount',
                                        'account_journal': journal.id,
                                        'account': journal.payment_debit_account_id.id,
                                        'paid_date': datetime.today().date()

                                    })


                                for ls in leds:
                                    ls.description = line.check_no + '=>' + 'Cleared',
                                    ls.credit += actual
                                    ls.account_journal = journal.id
                                    ls.account = journal.payment_debit_account_id.id
                                    ls.paid_date = datetime.today().date()

                                led = self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', 1)])
                                leds = self.env['partner.ledgers.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', 1)])
                                for l in led:
                                    # l.description = line.check_no + '=>' + 'Cleared',
                                    # l.credit += actual
                                    # l.balance = balance_amount-actual
                                    # l.account_journal = journal.id
                                    # l.account = journal.default_debit_account_id.id
                                    # l.paid_date = datetime.today().date()
                                    self.env['partner.ledger.customer'].sudo().create({
                                        'date': datetime.today().date(),
                                        'partner_id': line.partner_id.id,
                                        'company_id': 1,
                                        'credit': actual,
                                        'check_only': True,
                                        # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                        'balance': balance_amount - actual,
                                        'description': line.check_no + '=>' + 'Cleared Amount',
                                        'account_journal': journal.id,
                                        'account': journal.payment_debit_account_id.id,
                                        'paid_date': datetime.today().date()

                                    })

                                for ls in leds:
                                    ls.description = line.check_no + '=>' + 'Cleared',
                                    ls.credit += actual
                                    ls.account_journal = journal.id
                                    ls.account = journal.payment_debit_account_id.id
                                    ls.paid_date = datetime.today().date()

                    if stmt:
                        if amount:
                            if not self.env['account.move'].search([('partner_id','=',line.partner_id.id)]):
                                j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                                journal_sub = self.env['account.journal'].search([('name','=',journal.name),('company_id','=',line.debited_account.company_id.id)])
                                if line.holder_name:
                                    partner = line.holder_name
                                else:
                                    partner = line.partner_id

                                pay_id = self.env['account.payment'].create({'partner_id': partner.id,
                                                                             # 'amount': check_inv.amount_total,
                                                                             'amount': amount,
                                                                             'partner_type': 'customer',
                                                                             'company_id': line.debited_account.company_id.id,
                                                                             'payment_type': 'inbound',
                                                                             'payment_method_id': j.id,
                                                                             # 'journal_id': line.journal_id.id,
                                                                             'journal_id': journal_sub.id,
                                                                             'ref': line.check_no,

                                                                             })
                                pay_id_main = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                             # 'amount': check_inv.amount_total,
                                                                             'amount': amount,
                                                                             'partner_type': 'customer',
                                                                             'company_id': self.env.user.company_id.id,
                                                                             'payment_type': 'inbound',
                                                                             'payment_method_id': j.id,
                                                                             # 'journal_id': line.journal_id.id,
                                                                             'journal_id': journal.id,
                                                                             'ref': line.check_no,

                                                                             })
                                # pay_id.post()
                                pay_id.action_post()
                                # pay_id_main.post()
                                pay_id_main.action_post()

                                pay_id.action_cash_book()
                                pay_id_main.action_cash_book()
                                invoices = self.env['account.move'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', self.env.user.company_id.id), ('state', '!=', 'paid')])
                                if invoices.mapped('amount_residual'):
                                    balance_amount = sum(invoices.mapped('amount_residual'))
                                else:
                                    balance_amount = sum(invoices.mapped('amount_total'))
                                balance_amount += self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                                if self.env['partner.ledger.customer'].search(
                                    [('company_id', '=', self.env.user.company_id.id),
                                     ('partner_id', '=', line.partner_id.id)]):
                                    balance_amount = self.env['partner.ledger.customer'].search(
                                        [('company_id', '=', self.env.user.company_id.id),
                                         ('partner_id', '=', line.partner_id.id)])[-1].balance

                                self.env['partner.ledger.customer'].sudo().create({
                                    'date': datetime.today().date(),
                                    # 'invoice_id': m.id,
                                    'check_only': True,
                                    'partner_id': line.partner_id.id,
                                    # 'product_id': m.invoice_line_ids[0].product_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    # 'price_units': m.inv_mc_qty,
                                    # 'uom': m.invoice_line_ids[0].uom_id.id,
                                    # 'rate': m.invoice_line_ids[0].price_unit,
                                    # 'credit': amount,
                                    'credit': amount,
                                    # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                    'balance': balance_amount - amount,
                                    'description':  'Cheque No'+ '=>' + line.check_no,
                                    'account_journal': journal.id,
                                    'account': journal.payment_debit_account_id.id,
                                    'paid_date': datetime.today().date()

                                })
                                if partner:
                                        invoices = self.env['account.move'].search(
                                            [('partner_id', '=', partner.id),
                                             ('company_id', '=', journal_sub.company_id.id), ('state', '!=', 'paid')])
                                        if invoices.mapped('amount_residual'):
                                            balance_amount = sum(invoices.mapped('amount_residual'))
                                        else:
                                            balance_amount = sum(invoices.mapped('amount_total'))
                                        balance_amount += self.env['partner.ledger.customer'].search(
                                            [('partner_id', '=', partner.id),
                                             ('description', '=', 'Opening Balance')]).balance
                                        if self.env['partner.ledger.customer'].search(
                                                [('company_id', '=', journal_sub.company_id.id),
                                                 ('partner_id', '=',partner.id)]):
                                            balance_amount = self.env['partner.ledger.customer'].search(
                                                [('company_id', '=', journal_sub.company_id.id),
                                                 ('partner_id', '=', partner.id)])[-1].balance
                                        self.env['partner.ledger.customer'].sudo().create({
                                            'date': datetime.today().date(),
                                            # 'invoice_id': m.id,
                                            'check_only': True,
                                            'partner_id': partner.id,
                                            # 'product_id': m.invoice_line_ids[0].product_id.id,
                                            'company_id': line.debited_account.company_id.id,
                                            # 'price_units': m.inv_mc_qty,
                                            # 'uom': m.invoice_line_ids[0].uom_id.id,
                                            # 'rate': m.invoice_line_ids[0].price_unit,
                                            # 'credit': amount,
                                            'credit': amount,
                                            # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                            'balance': balance_amount - amount,
                                            'description':  'Cheque No'+ '=>' + line.check_no,
                                            'account_journal': journal.id,
                                            'account': journal.payment_debit_account_id.id,
                                            'paid_date': datetime.today().date()

                                        })
                                self.env['partner.ledgers.customer'].create({
                                    'date': datetime.today().date(),
                                    # 'invoice_id': m.id,
                                    'month': str(datetime.today().date().month),
                                    'partner_id': line.partner_id.id,
                                    # 'product_id': m.invoice_line_ids[0].product_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    # 'price_units': m.inv_mc_qty,
                                    # 'uom': m.invoice_line_ids[0].uom_id.id,
                                    # 'rate': m.invoice_line_ids[0].price_unit,
                                    'credit': amount,
                                    'debit': amount,
                                    'description': line.check_no + '=>' + 'Advance Amount',
                                    'account_journal': journal.id,
                                    'account': journal.payment_debit_account_id.id,
                                    'paid_date': datetime.today().date()

                                })
                                invoices = self.env['account.move'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', journal_sub.company_id.id), ('state', '!=', 'paid')])
                                if invoices.mapped('amount_residual'):
                                    balance_amount = sum(invoices.mapped('amount_residual'))
                                else:
                                    balance_amount = sum(invoices.mapped('amount_total'))
                                balance_amount += self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id),('company_id','=',journal_sub.company_id.id),('description', '=', 'Opening Balance')]).balance
                                if self.env['partner.ledger.customer'].search(
                                    [('company_id', '=', journal_sub.company_id.id),
                                     ('partner_id', '=', line.partner_id.id)]):
                                    balance_amount = self.env['partner.ledger.customer'].search(
                                                                [('company_id', '=', journal_sub.company_id.id),
                                                                 ('partner_id', '=', line.partner_id.id)])[-1].balance

                                self.env['partner.ledger.customer'].sudo().create({
                                                            'date': datetime.today().date(),
                                                            # 'invoice_id': m.id,
                                                            'check_only': True,
                                                            'partner_id': line.partner_id.id,
                                                            # 'product_id': m.invoice_line_ids[0].product_id.id,
                                                            'company_id': journal_sub.company_id.id,
                                                            # 'price_units': m.inv_mc_qty,
                                                            # 'uom': m.invoice_line_ids[0].uom_id.id,
                                                            # 'rate': m.invoice_line_ids[0].price_unit,
                                                            # 'credit': amount,
                                                            'credit': amount,
                                                            # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                                            'balance': balance_amount - amount,
                                                            'description':  'Cheque No'+ '=>' + line.check_no,
                                                            'account_journal': journal_sub.id,
                                                            'account': journal.payment_debit_account_id.id,
                                                            'paid_date': datetime.today().date()

                                                        })
                                self.env['partner.ledgers.customer'].create({
                                    'date': datetime.today().date(),
                                    # 'invoice_id': m.id,
                                    'month': str(datetime.today().date().month),
                                    'partner_id': line.partner_id.id,
                                    # 'product_id': m.invoice_line_ids[0].product_id.id,
                                    'company_id': journal_sub.company_id.id,
                                    # 'price_units': m.inv_mc_qty,
                                    # 'uom': m.invoice_line_ids[0].uom_id.id,
                                    # 'rate': m.invoice_line_ids[0].price_unit,
                                    'credit': amount,
                                    'debit': amount,
                                    'description': line.check_no + '=>' + 'Advance Amount',
                                    'account_journal': journal_sub.id,
                                    'account': journal.payment_debit_account_id.id,
                                    'paid_date': datetime.today().date()

                                })

                            else:

                                j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                                pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                             # 'amount': check_inv.amount_total,
                                                                             'amount': amount,
                                                                             'partner_type': 'customer',
                                                                             'company_id': self.env.user.company_id.id,
                                                                             'payment_type': 'inbound',
                                                                             'payment_method_id': j.id,
                                                                             # 'journal_id': line.journal_id.id,
                                                                             'journal_id': journal.id,
                                                                             'ref': line.check_no,

                                                                             })
                                # pay_id.post()
                                pay_id.action_post()
                                pay_id.action_cash_book()
                                invoices = self.env['account.move'].search(
                                    [('partner_id', '=', line.partner_id.id),
                                     ('company_id', '=', self.env.user.company_id.id),('state', '!=', 'paid')])
                                if invoices.mapped('amount_residual'):
                                    balance_amount = sum(invoices.mapped('amount_residual'))
                                else:
                                    balance_amount = sum(invoices.mapped('amount_total'))
                                balance_amount += self.env['partner.ledger.customer'].search(
                                    [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                                balance_amount = self.env['partner.ledger.customer'].search(
                                    [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])[-1].balance

                                self.env['partner.ledger.customer'].sudo().create({
                                    'date': datetime.today().date(),
                                    # 'invoice_id': m.id,
                                    'check_only': True,
                                    'partner_id': line.partner_id.id,
                                    # 'product_id': m.invoice_line_ids[0].product_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    # 'price_units': m.inv_mc_qty,
                                    # 'uom': m.invoice_line_ids[0].uom_id.id,
                                    # 'rate': m.invoice_line_ids[0].price_unit,
                                    # 'credit': amount,
                                    'credit': amount,
                                    # 'account_move': pay_id.move_line_ids.mapped('move_id')[0].id,
                                    'account_move': pay_id.move_id.id,
                                    'balance':balance_amount-amount,
                                    'description':  'Cheque No'+ '=>' + line.check_no,
                                    'account_journal': journal.id,
                                    'account': journal.payment_debit_account_id.id,
                                    'paid_date': datetime.today().date()

                                })
                                self.env['partner.ledgers.customer'].create({
                                    'date': datetime.today().date(),
                                    # 'invoice_id': m.id,
                                    'month':str(datetime.today().date().month),
                                    'partner_id': line.partner_id.id,
                                    # 'product_id': m.invoice_line_ids[0].product_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    # 'price_units': m.inv_mc_qty,
                                    # 'uom': m.invoice_line_ids[0].uom_id.id,
                                    # 'rate': m.invoice_line_ids[0].price_unit,
                                    'credit': amount,
                                    'debit': amount,
                                    'description': line.check_no + '=>' + 'Advance Amount',
                                    'account_journal': journal.id,
                                    'account': journal.payment_debit_account_id.id,
                                    'paid_date': datetime.today().date()

                                })

                        stmt.line_ids = payment_list
                        # stmt.button_post()
                        # # stmt.line_ids = payment_list
                        # # stmt.move_line_ids = pay_id_list
                        # stmt.write({'state': 'confirm'})
                        self.write({'state': 'validate'})
                else:
                    journal = self.env['account.journal'].search([('name', '=', 'Bank'), ('company_id', '=', 1)])
                    stmt1 = self.env['account.bank.statement']
                    j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                    if not stmt:
                        # _get_payment_info_JSON
                        # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.debited_account.id)]).mapped(
                        #     'debit'))

                        if self.env['account.bank.statement'].search([('company_id', '=', journal.company_id.id),
                                                                      ('journal_id', '=', journal.id)]):
                            bal = self.env['account.bank.statement'].search(
                                [('company_id', '=', journal.company_id.id),
                                 ('journal_id', '=', journal.id)])[0].balance_end_real
                        else:
                            bal = 0

                        stmt = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                          'balance_start': bal,
                                                                          # 'journal_id': line.journal_id.id,
                                                                          'journal_id': journal.id,
                                                                          'balance_end_real': bal + line.amount_total

                                                                          })
                        pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                     # 'amount': check_inv.amount_total,
                                                                     'amount': line.amount_total,
                                                                     'partner_type': 'customer',
                                                                     'company_id': self.env.user.company_id.id,
                                                                     'payment_type': 'inbound',
                                                                     'payment_method_id': j.id,
                                                                     # 'journal_id': line.journal_id.id,
                                                                     'journal_id': journal.id,
                                                                     'ref': line.check_no + '=>' + 'Cleared',

                                                                     })
                        # pay_id.post()
                        pay_id.action_post()
                        pay_id_list = []
                        # for k in pay_id.move_line_ids:
                        for k in pay_id.line_ids:
                            pay_id_list.append(k.id)
                    if not stmt1:
                        # _get_payment_info_JSON
                        # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.debited_account.id)]).mapped(
                        #     'debit'))

                        if self.env['account.bank.statement'].search([('company_id', '=', line.debited_account.company_id.id),
                                                                      ('journal_id', '=', line.debited_account.id)]):
                            bal = self.env['account.bank.statement'].search(
                                [('company_id', '=', line.debited_account.company_id.id),
                                 ('journal_id', '=', line.debited_account.id)])[0].balance_end_real
                        else:
                            bal = 0

                        stmt1 = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                          'balance_start': bal,
                                                                          # 'journal_id': line.journal_id.id,
                                                                          'journal_id': line.debited_account.id,
                                                                          'balance_end_real': bal + line.amount_total

                                                                          })
                        pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                     # 'amount': check_inv.amount_total,
                                                                     'amount': line.amount_total,
                                                                     'partner_type': 'customer',
                                                                     'company_id': self.env.user.company_id.id,
                                                                     'payment_type': 'inbound',
                                                                     'payment_method_id': j.id,
                                                                     # 'journal_id': line.journal_id.id,
                                                                     'journal_id': journal.id,
                                                                     'ref': line.check_no + '=>' + 'Cleared',

                                                                     })
                        pay_id_1 = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                     # 'amount': check_inv.amount_total,
                                                                     'amount': line.amount_total,
                                                                     'partner_type': 'customer',
                                                                     'company_id': line.debited_account.company_id.id,
                                                                     'payment_type': 'inbound',
                                                                     'payment_method_id': j.id,
                                                                     # 'journal_id': line.journal_id.id,
                                                                     'journal_id': line.debited_account.id,
                                                                     'ref': line.check_no + '=>' + 'Cleared',

                                                                     })
                        # pay_id.post()
                        # pay_id_1.post()
                        pay_id_1.action_post()
                        pay_id_list_1 = []
                        # for k in pay_id.move_line_ids:
                        #     pay_id_list.append(k.id)
                        for k in pay_id_1.line_ids:
                            pay_id_list_1.append(k.id)

                    payment_list = []
                    product_line = (0, 0, {
                        'date': line.date,
                        'name': line.check_no,
                        'partner_id': line.partner_id.id,
                        'payment_ref': line.check_no,
                        'amount': line.amount_total
                    })
                    payment_list.append(product_line)
                    if stmt:
                        stmt.line_ids = payment_list
                        stmt.move_line_ids = pay_id_list
                        # stmt.write({'state': 'confirm'})
                    if stmt1:
                        stmt1.line_ids = payment_list
                        stmt1.move_line_ids = pay_id_list_1
                        # stmt1.write({'state': 'confirm'})
                    invoices = self.env['account.move'].search(
                        [('partner_id', '=', line.partner_id.id), ('company_id', '=', journal.company_id.id),
                         ('state', '!=', 'paid')])
                    if invoices.mapped('amount_residual'):
                        balance_amount = sum(invoices.mapped('amount_residual'))
                    else:
                        balance_amount = sum(invoices.mapped('amount_total'))
                    balance_amount += self.env['partner.ledger.customer'].search(
                        [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                    preview = self.env['partner.ledger.customer'].search(
                        [('company_id', '=', journal.company_id.id), ('partner_id', '=', line.partner_id.id)])
                    if preview:
                        balance_amount = self.env['partner.ledger.customer'].search(
                            [('company_id', '=', journal.company_id.id), ('partner_id', '=', line.partner_id.id)])[
                            -1].balance
                    self.env['partner.ledger.customer'].sudo().create({
                        'date': datetime.today().date(),
                        'partner_id': line.partner_id.id,
                        'company_id': journal.company_id.id,
                        # 'account_move': pay_id.move_line_ids.mapped('move_id').id,
                        'account_move': pay_id.move_id.id,
                        'credit': line.amount_total,
                        'description': 'Cheque No' + '=>' + line.check_no,
                        'account_journal': journal.id,
                        'account': journal.payment_debit_account_id.id,
                        'paid_date': datetime.today().date(),
                        'balance': balance_amount - line.amount_total,
                    })

        if self.collection_type == "both":
            for line in self.bulk_all_lines:
                if line.amount_residual == 0.0:
                    raise UserError(_("Please mention paid amount for this partner %s ")%(line.partner_id.name))
                journal = line.debited_account
                if not stmt:
                    # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.journal_id.id)]).mapped(
                    #     'debit'))

                    if self.env['account.bank.statement'].search([('company_id', '=', line.journal_id.company_id.id),
                                                                  ('journal_id', '=', line.journal_id.id)]):
                        bal = self.env['account.bank.statement'].search(
                            [('company_id', '=', line.journal_id.company_id.id),
                             ('journal_id', '=', line.journal_id.id)])[0].balance_end_real
                    else:
                        bal = 0




                    stmt = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                      'balance_start': bal,
                                                                      # 'journal_id': line.journal_id.id,
                                                                      'journal_id': journal.id,
                                                                      # 'balance_end_real': line.amount_total
                                                                      'balance_end_real': bal+line.amount_total

                                                                      })

                payment_list = []
                pay_id_list = []
                account = self.env['account.move'].search([('company_id','=',self.env.user.company_id.id),('partner_id','=',line.partner_id.id),('state','=','posted')])
                amount = line.amount_total
                actual =0
                for check_inv in account:
                    if amount:
                        if check_inv.amount_residual >= amount:
                            actual=amount
                            product_line = (0, 0, {
                                'date': line.payment_date,
                                'name': check_inv.display_name,
                                'partner_id': line.partner_id.id,
                                'payment_ref': check_inv.display_name,
                                'amount': amount
                            })
                            amount = amount - amount
                            payment_list.append(product_line)
                        else:
                            if check_inv.amount_residual != 0:
                                amount = amount-check_inv.amount_residual
                                actual =check_inv.amount_residual
                                product_line = (0, 0, {
                                    'date': line.payment_date,
                                    'name': check_inv.display_name,
                                    'partner_id': line.partner_id.id,
                                    'payment_ref': check_inv.display_name,
                                    'amount': check_inv.amount_residual
                                })
                                payment_list.append(product_line)

                        j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]

                        pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                                     # 'amount': check_inv.amount_total,
                                                                     'amount': actual,
                                                                     'partner_type': 'customer',
                                                                     'company_id': self.env.user.company_id.id,
                                                                     'payment_type': 'inbound',
                                                                     'payment_method_id': j.id,
                                                                     # 'journal_id': line.journal_id.id,
                                                                     'journal_id': journal.id,
                                                                     'ref': 'All Collection',
                                                                     # 'invoice_ids': [(6, 0, check_inv.ids)]
                                                                     # 'move_id': check_inv.ids
                                                                     })
                        # pay_id.action_validate_invoice_payment()
                        pay_id.action_post()
                        # for k in pay_id.move_line_ids:
                        for k in pay_id.line_ids:
                            pay_id_list.append(k.id)
                        # line.payments += pay_id
                        executive_rec = self.env['collection.cheque'].search([('check_line','=',line.check_line.id)])
                        # executive_rec.amount_total += line.amount_total
                        if executive_rec:
                            executive_rec.al_state =True
                        executive_coll_rec = self.env['executive.collection.record'].search(
                            [('collection_line_id', '=', line.collection_line.id)])
                        if executive_coll_rec:
                            executive_coll_rec.al_state = True
            if stmt:
                stmt.line_ids = payment_list
                # stmt.move_line_ids = pay_id_list
                # stmt.button_post()
                # stmt.write({'state': 'confirm'})
                self.write({'state': 'validate'})
