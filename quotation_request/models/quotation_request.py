from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.mail.models.mail_thread import MailThread

class QuotationRequest(models.Model, MailThread):
    _name = 'quotation.request'
    _description = 'Quotation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.today)
    delivery_deadline = fields.Date(string='Delivery Deadline')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('validated', 'Validated'),
        ('quotation_sent', 'Quotation Sent'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many('quotation.request.line', 'request_id', string='Request Lines')
    purchase_order_id = fields.Many2one('purchase.order', string='Related RFQ/Purchase Order')
    message_follower_ids = fields.One2many('mail.followers', 'res_id', string='Followers')
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')
    quotation_id = fields.Many2one('sale.order', string='Generated Quotation', readonly=True)
    user_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user)
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id', readonly=True)
    amount_total = fields.Monetary(string='Total Amount', compute='_compute_amount_total', store=True, currency_field='currency_id')

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(request.line_ids.mapped('price_subtotal'))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('quotation.request') or _('New')
        return super(QuotationRequest, self).create(vals)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_validate(self):
        for request in self:
            if request.state != 'submitted':
                raise UserError(_("Only submitted requests can be validated."))
            request.write({'state': 'validated'})

    def generate_quotation(self):
        self.ensure_one()
        if self.state != 'validated':
            raise UserError(_("Only validated requests can generate quotations."))

        SaleOrder = self.env['sale.order']
        order_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'product_uom_qty': line.quantity,
            'price_unit': line.price_unit,
        }) for line in self.line_ids]

        quotation = SaleOrder.create({
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'order_line': order_lines,
            'state': 'draft',
        })

        self.write({
            'state': 'quotation_sent',
            'quotation_id': quotation.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_quotation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.quotation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('name', 'partner_id')
    def _compute_quotation_id(self):
        for record in self:
            quotation = self.env['sale.order'].search([
                ('origin', '=', record.name),
                ('partner_id', '=', record.partner_id.id),
            ], limit=1)
            record.quotation_id = quotation.id if quotation else False

    def action_confirm_quotation(self):
        self.ensure_one()
        if self.quotation_id and self.quotation_id.state == 'draft':
            self.quotation_id.action_confirm()
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        for request in self:
            if request.state in ['cancelled', 'quotation_sent']:
                raise UserError(_("Cannot cancel a request that is already cancelled or has a quotation sent."))
            request.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        for request in self:
            if request.state != 'cancelled':
                raise UserError(_("Only cancelled requests can be reset to draft."))
            request.write({'state': 'draft'})

class QuotationRequestLine(models.Model):
    _name = 'quotation.request.line'
    _description = 'Quotation Request Line'

    request_id = fields.Many2one('quotation.request', string='Quotation Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id', depends=['request_id.currency_id'], store=True, string='Currency')

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.list_price
