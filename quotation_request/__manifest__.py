{
    'name': 'Quotation Request',
    'version': '1.0',
    'summary': 'Module for managing quotation requests',
    'description': 'This module allows users to create and manage quotation requests.',
    'category': 'Sales',
    'author': 'DFWIT Partner',
    'website': 'https://www.abc.com',
    'license': 'LGPL-3',
    'depends': ['base', 'sale', 'purchase', 'portal', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/rfq.xml',
        'views/quotation_req.xml',
        'templates/portal_templates.xml', 
    ],
    'assets': {
        'web.assets_backend': [
            'quotation_request/static/src/img/quot.png',
            'quotation_request/static/src/css/addProduct.css',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}