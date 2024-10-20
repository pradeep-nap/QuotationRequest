from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.mail.models.mail_thread import MailThread

class QuotationRequest(models.Model, MailThread):
    _name = 'quotation.request'
    _description = 'Quotation Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.today, required=True)
    delivery_deadline = fields.Date(string='Delivery Deadline')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    amount_total = fields.Float(string='Total Amount', compute='_compute_amount_total', store=True)
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user)
    quotation_id = fields.Many2one('sale.order', string='Quotation', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('quotation_generated', 'Quotation Generated'),
        ('quotation_sent', 'Quotation Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    line_ids = fields.One2many('quotation.request.line', 'request_id', string='Request Lines')

    @api.depends('quotation_id.amount_total')
    def _compute_amount_total(self):
        for request in self:
            if request.quotation_id:
                request.amount_total = request.quotation_id.amount_total
            else:
                request.amount_total = 0.0

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('quotation.request') or 'New'
        return super(QuotationRequest, self).create(vals)

    def action_validate(self):
        for record in self:
            if record.state == 'draft':
                record.write({'state': 'validated'})

    def action_generate_quotation(self):
        self.ensure_one()
        if self.state != 'validated':
            raise UserError(_("You can only generate a quotation for validated requests."))

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
            'state': 'quotation_generated',
            'quotation_id': quotation.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_quotation(self):
        self.ensure_one()
        if self.state != 'quotation_generated':
            raise UserError(_("You can only send quotations that have been generated."))
        # Add logic here to send the quotation (e.g., email)
        self.write({'state': 'quotation_sent'})

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

    def action_accept_quotation(self):
        self.ensure_one()
        if self.state != 'quotation_sent':
            raise UserError(_("You can only accept quotations that have been sent."))
        if self.quotation_id and self.quotation_id.state == 'draft':
            self.quotation_id.action_confirm()
        self.write({'state': 'accepted'})

    def action_reject_quotation(self):
        self.ensure_one()
        if self.state != 'quotation_sent':
            raise UserError(_("You can only reject quotations that have been sent."))
        self.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _get_state_label(self):
        states_dict = dict(self._fields['state'].selection)
        return states_dict.get(self.state, '')

    display_state = fields.Char(string='Display State', compute='_compute_display_state')

    @api.depends('state')
    def _compute_display_state(self):
        for record in self:
            record.display_state = record._get_state_label()

    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True)

    def action_accept(self):
        self.ensure_one()
        if self.state == 'quotation_sent':
            if not self.quotation_id:
                # Create a new quotation if it doesn't exist
                quotation = self.env['sale.order'].create({
                    'partner_id': self.partner_id.id,
                    'date_order': fields.Datetime.now(),
                    'origin': self.name,
                    # Add other necessary fields
                })

                # Create quotation lines
                for line in self.line_ids:
                    self.env['sale.order.line'].create({
                        'order_id': quotation.id,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.unit_price,
                        # Add other necessary fields
                    })

                self.quotation_id = quotation
            else:
                quotation = self.quotation_id

            # Update the quotation request state
            self.write({
                'state': 'accepted',
            })

            # Confirm the quotation
            quotation.action_confirm()

            # Redirect to the quotation page
            return {
                'type': 'ir.actions.act_url',
                'url': f'/my/quotes/{quotation.id}',
                'target': 'self',
            }
        else:
            raise UserError(_("You can only accept quotations that have been sent."))

    def action_reject(self):
        self.ensure_one()
        if self.state == 'quotation_sent':
            self.write({'state': 'rejected'})

    def action_view_sale_order(self):
        self.ensure_one()
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': self.sale_order_id.id,
                'target': 'current',
            }
        return True

    @api.constrains('state', 'quotation_id')
    def _check_quotation_state(self):
        for record in self:
            if record.state in ['draft', 'validated'] and record.quotation_id:
                raise ValidationError(_("A quotation cannot exist for a request in draft or validated state."))

    def action_view_sales_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
        }

    # You'll need to implement the logic to convert quotation to sales order
    # This could be in a separate method called from your controller
    def convert_to_sales_order(self):
        self.ensure_one()
        if self.state == 'quotation_sent' and self.quotation_id:
            sale_order = self.quotation_id.action_confirm()
            self.write({
                'state': 'sales_order',
                'sale_order_id': sale_order.id,
            })

class QuotationRequestLine(models.Model):
    _name = 'quotation.request.line'
    _description = 'Quotation Request Line'

    request_id = fields.Many2one('quotation.request', string='Quotation Request')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
