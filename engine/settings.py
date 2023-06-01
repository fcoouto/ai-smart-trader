# VALIDATION
MIN_BALANCE = 100

# TRADING
MAX_TRADE_AMOUNT_PER_POSITION = 3
MARTINGALE_MULTIPLIER = 2
OPTIMAL_TRADE_SIZE_PCT = 0.5
MAX_TRADE_SIZE_PCT = 3

# DEBUG
DEBUG_OCR = True
DEBUG_CHART = True
# CORE
LOCATE_CONFIDENCE = 0.90
PROGRESS_BAR_SLEEP_TIME = 0.250
SS_PATH = 'ss\\'
SS_TEMPLATE_PATH = 'ss\\template\\'
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
CORE_DATA = {
    'asset': 'string',
    'balance': 'float',
    'ohlc': 'string',
    'ema_72': 'float',
    'rsi': 'float',
    'trade_amount': 'float',
    'payout': 'percentage',
    'expiry_time': 'time',
}
BROKERS = {
    'iqcent': {
        'id': 'iqcent',
        'name': 'IQ Cent',
        'zones': {
            'header': {
                'id': 'header',
                'region': None,
                'locate_confidence': 0.75,
                'is_mandatory': True,
                'has_login_info': True,
                'elements': ['asset', 'balance']
            },
            'chart_top': {
                'id': 'chart_top',
                'region': None,
                'locate_confidence': 0.70,
                'is_mandatory': True,
                'elements': ['ohlc', 'ema_72'],
            },
            'chart_bottom': {
                'id': 'chart_bottom',
                'region': None,
                'locate_confidence': 0.75,
                'is_mandatory': True,
                'elements': ['rsi']
            },
            'footer': {
                'id': 'footer',
                'region': None,
                'locate_confidence': 0.75,
                'is_mandatory': True,
                'elements': ['trade_amount', 'payout', 'expiry_time']
            },
            'tick_header': {
                'id': 'tick_header',
                'region': None,
                'locate_confidence': 0.75,
            },
            'dp_item_1min': {
                'id': 'dp_item_1min',
                'region': None,
                'locate_confidence': 0.95,
            },
            'drawing_toolbar': {
                'context': 'tv',
                'id': 'drawing_toolbar',
                'region': None,
                'locate_confidence': 0.90,
            },
            'menu_chart': {
                'context': 'tv',
                'id': 'menu_chart',
                'region': None,
                'locate_confidence': 0.90,
            },
            'navbar_chart_settings': {
                'context': 'tv',
                'id': 'navbar_chart_settings',
                'region': None,
                'locate_confidence': 0.75,
            },
            'chart_settings_tab1_top': {
                'context': 'tv',
                'id': 'chart_settings_tab1_top',
                'region': None,
                'locate_confidence': 0.80,
            },
            'chart_settings_tab2_top': {
                'context': 'tv',
                'id': 'chart_settings_tab2_top',
                'region': None,
                'locate_confidence': 0.90,
            },
            'chart_settings_tab2_bottom': {
                'context': 'tv',
                'id': 'chart_settings_tab2_bottom',
                'region': None,
                'locate_confidence': 0.90,
            },
            'colors_opacity': {
                'context': 'tv',
                'id': 'colors_opacity',
                'region': None,
                'locate_confidence': 0.90,
            },
            'navbar_ema_settings': {
                'context': 'tv',
                'id': 'navbar_ema_settings',
                'region': None,
                'locate_confidence': 0.75,
            },
            'ema_settings_tab1': {
                'context': 'tv',
                'id': 'ema_settings_tab1',
                'region': None,
                'locate_confidence': 0.80,
            },
            'ema_settings_tab2': {
                'context': 'tv',
                'id': 'ema_settings_tab2',
                'region': None,
                'locate_confidence': 0.80,
            },
            'navbar_rsi_settings': {
                'context': 'tv',
                'id': 'navbar_rsi_settings',
                'region': None,
                'locate_confidence': 0.75,
            },
            'rsi_settings_tab1': {
                'context': 'tv',
                'id': 'rsi_settings_tab1',
                'region': None,
                'locate_confidence': 0.80,
            },
            'rsi_settings_tab2': {
                'context': 'tv',
                'id': 'rsi_settings_tab2',
                'region': None,
                'locate_confidence': 0.80,
            },
        },
        'elements': {
            'area_chart_background': {
                'context': 'tv',
                'zone': 'drawing_toolbar',
                'x': None,
                'y': None
            },
            'lbl_chart_asset': {
                'context': 'tv',
                'zone': 'drawing_toolbar',
                'x': None,
                'y': None
            },
            'btn_chart_remove_indicators': {
                'context': 'tv',
                'zone': 'menu_chart',
                'x': None,
                'y': None
            },
            'btn_chart_settings': {
                'context': 'tv',
                'zone': 'menu_chart',
                'x': None,
                'y': None
            },
            'btn_chart_type_candle': {
                'zone': 'tick_header',
                'x': None,
                'y': None
            },
            'btn_chart_timeframe': {
                'zone': 'header',
                'x': None,
                'y': None
            },
            'btn_chart_indicators': {
                'zone': 'header',
                'x': None,
                'y': None
            },
            'btn_ema_settings': {
                'zone': 'chart_top',
                'x': None,
                'y': None
            },
            'btn_rsi_settings': {
                'context': 'tv',
                'zone': 'drawing_toolbar',
                'x': None,
                'y': None
            },
            'checkbox_chart_settings_bar_change_values': {
                'context': 'tv',
                'zone': 'chart_settings_tab2_top',
                'x': None,
                'y': None
            },
            'checkbox_rsi_settings_upper_limit': {
                'context': 'tv',
                'zone': 'rsi_settings_tab2',
                'x': None,
                'y': None
            },
            'checkbox_rsi_settings_lower_limit': {
                'context': 'tv',
                'zone': 'rsi_settings_tab2',
                'x': None,
                'y': None
            },
            'checkbox_rsi_settings_hlines_bg': {
                'context': 'tv',
                'zone': 'rsi_settings_tab2',
                'x': None,
                'y': None
            },
            'item_color_white': {
                'context': 'tv',
                'zone': 'colors_opacity',
                'x': None,
                'y': None
            },
            'input_color_opacity': {
                'context': 'tv',
                'zone': 'colors_opacity',
                'x': None,
                'y': None
            },
            'input_chart_settings_body_green': {
                'context': 'tv',
                'zone': 'chart_settings_tab1_top',
                'x': None,
                'y': None
            },
            'input_chart_settings_body_red': {
                'context': 'tv',
                'zone': 'chart_settings_tab1_top',
                'x': None,
                'y': None
            },
            'input_chart_settings_wick_green': {
                'context': 'tv',
                'zone': 'chart_settings_tab1_top',
                'x': None,
                'y': None
            },
            'input_chart_settings_wick_red': {
                'context': 'tv',
                'zone': 'chart_settings_tab1_top',
                'x': None,
                'y': None
            },
            'input_ema_settings_color': {
                'context': 'tv',
                'zone': 'ema_settings_tab2',
                'x': None,
                'y': None
            },
            'input_ema_settings_length': {
                'context': 'tv',
                'zone': 'ema_settings_tab1',
                'x': None,
                'y': None
            },
            'input_rsi_settings_color': {
                'context': 'tv',
                'zone': 'rsi_settings_tab2',
                'x': None,
                'y': None
            },
            'input_rsi_settings_length': {
                'context': 'tv',
                'zone': 'rsi_settings_tab1',
                'x': None,
                'y': None
            },
            'navitem_ema_settings_tab1': {
                'context': 'tv',
                'zone': 'navbar_ema_settings',
                'x': None,
                'y': None
            },
            'navitem_ema_settings_tab2': {
                'context': 'tv',
                'zone': 'navbar_ema_settings',
                'x': None,
                'y': None
            },
            'navitem_chart_settings_tab1': {
                'context': 'tv',
                'zone': 'navbar_chart_settings',
                'x': None,
                'y': None
            },
            'navitem_chart_settings_tab2': {
                'context': 'tv',
                'zone': 'navbar_chart_settings',
                'x': None,
                'y': None
            },
            'slider_background_opacity': {
                'context': 'tv',
                'zone': 'chart_settings_tab2_bottom',
                'x': None,
                'y': None
            },
            'navitem_rsi_settings_tab1': {
                'context': 'tv',
                'zone': 'navbar_rsi_settings',
                'x': None,
                'y': None
            },
            'navitem_rsi_settings_tab2': {
                'context': 'tv',
                'zone': 'navbar_rsi_settings',
                'x': None,
                'y': None
            },
            'trade_amount': {
                'zone': 'footer',
                'x': None,
                'y': None
            },
            'btn_expiry_time': {
                'zone': 'footer',
                'type': 'float',
                'x': None,
                'y': None
            },
            'dp_item_1min': {
                'context': 'iqcent',
                'zone': 'dp_item_1min',
                'x': None,
                'y': None
            },
            'btn_up': {
                'id': 'trade_amount',
                'zone': 'footer',
                'type': 'float',
                'x': None,
                'y': None
            },
            'btn_down': {
                'id': 'trade_amount',
                'zone': 'footer',
                'type': 'float',
                'x': None,
                'y': None
            },
        }
    }
}
