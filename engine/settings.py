import os
import platform


# DEBUG
DEBUG_OCR = True
DEBUG_MSG = True

# VALIDATION
MIN_BALANCE = 100
MIN_TRADE_SIZE = 1.00

# TRADING
TRADING_STRATEGIES = ['ema_rsi_50',
                      'ema_rsi_8020']
MODE_SIMULATION = 'simulation'
MODE_DEMO = 'demo'
MODE_LIVE = 'live'
MAX_TRADES_PER_POSITION = 3
MARTINGALE_MULTIPLIER = [1, 2, 1]
AMOUNT_TRADES_TO_RECOVER_LOSSES = 3

# EXTRAS
PROGRESS_BAR_WAITING_TIME = 3
PROGRESS_BAR_INTERVAL_TIME = 0.250

# CORE
LOCATE_CONFIDENCE = 0.85
MAX_TRIES_READING_ELEMENT = 3
PLAYBOOK_LONG_ACTION = {
    'go_to_url': 7,
    'go_to_trading_page': 7,
    'iqcent_chart_setup': 30,
    'log_in': 10,
    'refresh_page': 7,
    'set_expiry_time': 5,
    'tv_reset': 10,
}
PATH_LOCK = 'lock'
LOCK_LONG_ACTION_FILENAME = 'long_action'
LOCK_FILE_EXTENSION = '.lck'
PATH_DATA = 'data'
PATH_SS = 'ocr'
PATH_SS_TEMPLATE = os.path.join(PATH_SS, 'template')
PATH_SS_CONFIG = os.path.join(os.getcwd(), 'ocr', 'config')
SS_FILE_EXTENSION = '.png'

if platform.system().lower() == 'windows':
    PATH_TESSERACT = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
elif platform.system().lower() == 'linux':
    PATH_TESSERACT = '/usr/bin/tesseract'

CORE_DATA = {
    'asset': 'string',
    'balance': 'currency',
    'ema_72': 'float',
    'expiry_time': 'time',
    'ohlc': 'string_ohlc',
    'payout': 'percentage',
    'rsi': 'float',
    'trade_size': 'float',
}
BROKERS = {
    'iqcent': {
        'id': 'iqcent',
        'name': 'IQ Cent',
        'url': 'https://iqcent.com/option/',
        'neutral_zones': {
            'within_app': {
                'width_pct': 0.50,
                'height_pct': 0.66
            },
            'bellow_app': {
                'width_pct': 0.50,
                'height_pct': 0.90
            }

        },
        'zones': {
            'header': {
                'id': 'header',
                'region': None,
                'locate_confidence': 0.90,
                'is_mandatory': True,
                'has_login_info': True,
                'elements': ['balance', 'asset']
            },
            'chart_top': {
                'id': 'chart_top',
                'region': None,
                'locate_confidence': 0.75,
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
                'elements': ['trade_size', 'payout', 'expiry_time']
            },
            'navbar_url': {
                'context': 'chrome',
                'id': 'navbar_url',
                'region': None,
                'locate_confidence': 0.80,
            },
            'modal_login': {
                'id': 'modal_login',
                'region': None,
                'locate_confidence': 0.85,
            },
            'tick_header': {
                'id': 'tick_header',
                'region': None,
                'locate_confidence': 0.80,
            },
            'header_logged_out': {
                'id': 'header_logged_out',
                'region': None,
                'locate_confidence': 0.80,
            },
            'dp_item_1min': {
                'id': 'dp_item_1min',
                'region': None,
                'locate_confidence': 0.90,
            },
            'drawing_toolbar': {
                'context': 'tv',
                'id': 'drawing_toolbar',
                'region': None,
                'locate_confidence': 0.85,
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
                'locate_confidence': 0.55,
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
                'locate_confidence': 0.80,
            },
            'chart_settings_tab2_bottom': {
                'context': 'tv',
                'id': 'chart_settings_tab2_bottom',
                'region': None,
                'locate_confidence': 0.80,
            },
            'chart_settings_tab4_top': {
                'context': 'tv',
                'id': 'chart_settings_tab4_top',
                'region': None,
                'locate_confidence': 0.80,
            },
            'colors_opacity': {
                'context': 'tv',
                'id': 'colors_opacity',
                'region': None,
                'locate_confidence': 0.80,
            },
            'navbar_ema_settings': {
                'context': 'tv',
                'id': 'navbar_ema_settings',
                'region': None,
                'locate_confidence': 0.60,
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
            'btn_login': {
                'zone': 'header_logged_out',
                'x': None,
                'y': None
            },
            'btn_login_confirm': {
                'zone': 'modal_login',
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
            'item_color_black': {
                'context': 'tv',
                'zone': 'colors_opacity',
                'x': None,
                'y': None
            },
            'item_color_white': {
                'context': 'tv',
                'zone': 'colors_opacity',
                'x': None,
                'y': None
            },
            'input_email': {
                'zone': 'modal_login',
                'x': None,
                'y': None
            },
            'input_pwd': {
                'zone': 'modal_login',
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
            'input_chart_settings_background': {
                'context': 'tv',
                'zone': 'chart_settings_tab4_top',
                'x': None,
                'y': None
            },
            'input_chart_settings_grid_lines_v': {
                'context': 'tv',
                'zone': 'chart_settings_tab4_top',
                'x': None,
                'y': None
            },
            'input_chart_settings_grid_lines_h': {
                'context': 'tv',
                'zone': 'chart_settings_tab4_top',
                'x': None,
                'y': None
            },
            'input_ema_settings_color': {
                'context': 'tv',
                'zone': 'ema_settings_tab2',
                'x': None,
                'y': None
            },
            'input_ema_settings_precision': {
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
            'navitem_chart_settings_tab4': {
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
            'trade_size': {
                'zone': 'footer',
                'x': None,
                'y': None
            },
            'close': {
                'zone': 'footer',
                'type': 'float',
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
            'dp_item_6': {
                'context': 'tv',
                'zone': 'dp_item_6',
                'x': None,
                'y': None
            },
            'btn_call': {
                'zone': 'footer',
                'type': 'float',
                'x': None,
                'y': None
            },
            'btn_put': {
                'zone': 'footer',
                'type': 'float',
                'x': None,
                'y': None
            },
            'alert_session_ended': {
                'context': 'iqcent',
                'zone': 'alert_session_ended',
                'x': None,
                'y': None
            },
            'alert_gain': {
                'context': 'iqcent',
                'zone': 'alert_gain',
                'x': None,
                'y': None
            },
            'alert_loss': {
                'context': 'iqcent',
                'zone': 'alert_loss',
                'x': None,
                'y': None
            },
            'alert_not_in_sync': {
                'context': 'iqcent',
                'zone': 'alert_not_in_sync',
                'x': None,
                'y': None
            },
            'input_url': {
                'context': 'chrome',
                'zone': 'navbar_url',
                'x': None,
                'y': None
            },
        }
    }
}
