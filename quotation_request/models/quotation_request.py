from odoo import models, fields, api
from odoo.addons.mail.models.mail_thread import MailThread

class QuotationRequest(models.Model, MailThread):
    _name = 'quotation.request'
    _description = 'Quotation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.today)
    delivery_deadline = fields.Date(string='Delivery Deadline')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('validated', 'Validated'),
        ('quotation_sent', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft')
    line_ids = fields.One2many('quotation.request.line', 'request_id', string='Request Lines')
    purchase_order_id = fields.Many2one('purchase.order', string='Related RFQ/Purchase Order')
    message_follower_ids = fields.One2many('mail.followers', 'res_id', string='Followers')
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages')
    quotation_id = fields.Many2one('sale.order', string='Generated Quotation', readonly=True)
    user_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('quotation.request') or 'New'
        vals['state'] = 'submitted'
        return super(QuotationRequest, self).create(vals)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_validate(self):
        self.ensure_one()
        if self.state == 'submitted':
            self.state = 'validated'
            # Add any additional logic for validation here

    def action_create_rfq(self):
        self.ensure_one()
        if self.state != 'validated':
            return

        PurchaseOrder = self.env['purchase.order']
        order_lines = []
        for line in self.line_ids:
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.quantity,
                'product_uom': line.product_id.uom_po_id.id,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Date.today(),
            }))

        rfq = PurchaseOrder.create({
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'order_line': order_lines,
        })

        self.write({
            'state': 'rfq_created',
            'purchase_order_id': rfq.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': rfq.id,
            'view_mode': 'form',
            'target': 'current',
        }
    def action_confirm_rfq(self):
        if self.purchase_order_id and self.purchase_order_id.state == 'draft':
            self.purchase_order_id.button_confirm()
            self.write({'state': 'confirmed'})

    def generate_quotation(self):
        self.ensure_one()
        if self.state != 'validated':
            return

        SaleOrder = self.env['sale.order']
        order_lines = []
        for line in self.line_ids:
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.product_id.list_price,
            }))

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

class QuotationRequestLine(models.Model):
    _name = 'quotation.request.line'
    _description = 'Quotation Request Line'

    request_id = fields.Many2one('quotation.request', string='Quotation Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
