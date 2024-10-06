{
    'name': 'Quotation Request',
    'version': '1.0',
    'summary': 'Manage quotation requests',
    'sequence': -100,
    'description': """Quotation Request Management System""",
    'category': 'Sales',
    'website': 'https://www.yourwebsite.com',
    'depends': ['base', 'sale', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/rfq.xml',
        'views/quotation_req.xml',
        'views/assests.xml',
        'templates/portal_templates.xml', 
        'views/portal_quot.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'quotation_request/static/src/img/quot.png',
            'quotation_request/static/src/css/addProduct.css',
        ],
        'web.assets_frontend': [
            '/quotation_request/static/src/css/addProduct.css',
        ],
    },
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}