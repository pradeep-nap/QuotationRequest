from odoo import http, fields
from odoo.http import request 

class QuotationRequestController(http.Controller):

    @http.route('/my/quotations', type='http', auth='user', website=True)
    def list_quotation_requests(self, **kw):
        requests = request.env['quotation.request'].search([('partner_id', '=', request.env.user.partner_id.id)])
        state_mapping = {
            'draft': 'Draft',
            'submitted': 'Submitted',
            'validated': 'Validated',
            'rfq_created': 'RFQ Created',
            'confirmed': 'Confirmed',
            'rejected': 'Rejected'
        }
        return request.render('quotation_request.quotation_request_list', {
            'requests': requests,
            'state_mapping': state_mapping
        })

    @http.route('/my/quotations/new', type='http', auth='user', website=True)
    def new_quotation_request(self, **kw):
        products = request.env['product.product'].search([('sale_ok', '=', True)])
        min_date = fields.Date.today()  
        return request.render('quotation_request.create_quotation_request', {
            'products': products,
            'min_date': min_date,
        })

    @http.route('/my/quotations/submit', type='http', auth='user', website=True, methods=['POST'])
    def submit_quotation_request(self, **post):
        partner_id = request.env.user.partner_id.id
        line_count = int(post.get('line_count', 0))
        
        values = {
            'partner_id': partner_id,
            'delivery_deadline': post.get('delivery_deadline'),
            'line_ids': []
        }

        for i in range(line_count):
            product_id = post.get(f'product_id_{i}')
            quantity = post.get(f'quantity_{i}')
            
            if product_id and quantity:
                product = request.env['product.product'].sudo().browse(int(product_id))
                values['line_ids'].append((0, 0, {
                    'product_id': int(product_id),
                    'quantity': float(quantity),
                    'product_uom': product.uom_id.id,
                }))

        if values['line_ids']:
            quotation_request = request.env['quotation.request'].sudo().create(values)
            return request.redirect('/my/quotations')
        else:
            return request.redirect('/my/quotations/create?error=no_products')

    @http.route('/my/quotations/<int:request_id>', type='http', auth='user', website=True)
    def view_quotation_request(self, request_id, **kw):
        quotation_request = request.env['quotation.request'].sudo().search([
            ('id', '=', request_id),
            ('partner_id', '=', request.env.user.partner_id.id),
        ], limit=1)
        if not quotation_request:
            return request.redirect('/my/quotations')
        
        # Force computation of quotation_id
        quotation_request._compute_quotation_id()
        
        return request.render('quotation_request.view_quotation_request', {
            'quotation_request': quotation_request,
        })

    @http.route(['/my/quotations/<int:quotation_id>/validate'], type='http', auth="user", website=True)
    def validate_quotation_request(self, quotation_id, **post):
        quotation_request = request.env['quotation.request'].sudo().browse(quotation_id)
        if quotation_request.exists() and quotation_request.state in ['draft', 'submitted']:
            quotation_request.action_validate()
        return request.redirect('/my/quotations/%s' % quotation_id)
