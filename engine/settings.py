import os
import platform
import tempfile


# DEBUG
DEBUG_OCR = False
DEBUG_HISTORY = True
DEBUG_PERFORMANCE = True

# VALIDATION
MIN_BALANCE = 100
#   CHART_DATA_SECONDS is about [ohlc, ema, rsi] values that should be stored in a list.
#   They must represent the closing of a candle.
CHART_DATA_MIN_SECONDS = 58
CHART_DATA_MAX_SECONDS = 7
CHART_DATA_READING_LIMIT_SECONDS = 5
REFRESH_PAGE_EVERY_MINUTES = 15

# TRADING
TRADING_STRATEGIES = ['ema_rsi_8020']
MODE_SIMULATION = 'simulation'
MODE_DEMO = 'demo'
MODE_LIVE = 'live'
MAX_TRADES_PER_POSITION = 3
MARTINGALE_MULTIPLIER = [1, 2.05, 1.10]
# MARTINGALE_MULTIPLIER = [1, 1, 1]
AMOUNT_TRADES_TO_RECOVER_LOSSES = 2
INITIAL_TRADE_AMOUNT_MULTIPLIER_FOR_STOP_LOSS = 60

# EXTRAS
PROGRESS_BAR_WAITING_TIME = 3
PROGRESS_BAR_INTERVAL_TIME = 0.250

# CORE
LOCATE_CONFIDENCE = 0.85
MAX_TRIES_READING_ELEMENT = 60
MAX_TRIES_LOCATING_ELEMENT = 5
PLAYBOOK_LONG_ACTION = {
    'activate_super_strike': 5,
    'go_to_url': 7,
    'go_to_trading_page': 7,
    'iqcent_chart_setup': 35,
    'log_in': 30,
    'read_past_candles': 10,
    'refresh_page': 7,
    'set_trade_size': 2,
    'set_expiry_time': 5,
    'toggle_expiry_time': 2,
    'tv_reset': 10,
}
PATH_LOCK = 'lock'
LOCK_FILE_EXTENSION = '.lck'
LOCK_LONG_ACTION_FILENAME = 'long_action'
PATH_DATA = 'data'
PATH_DATA_CHART = os.path.join(PATH_DATA, 'chart')
PATH_SS = 'ocr'
PATH_SS_TEMPLATE = os.path.join(PATH_SS, 'template', platform.system().lower())
PATH_SS_CONFIG = os.path.join(os.getcwd(), 'ocr', 'config')
SS_FILE_EXTENSION = '.png'
PATH_TEMP = tempfile.gettempdir()
PATH_TEMP_BROWSER_PROFILES = os.path.join(PATH_TEMP, 'google', 'chrome')

if platform.system().lower() == 'windows':
    PATH_TESSERACT = os.path.join('C:\\', 'Program Files', 'Tesseract-OCR', 'tesseract.exe')

    PATH_BROWSER = os.path.join('C:\\', 'Program Files (x86)', 'Google', 'Chrome', 'Application', 'chrome.exe')
    BROWSER_WIDTH = 654
    BROWSER_HEIGHT = 838
elif platform.system().lower() == 'linux':
    PATH_TESSERACT = os.path.join('/usr', 'bin', 'tesseract')

    PATH_BROWSER = os.path.join('/opt', 'google', 'chrome', 'google-chrome')
    BROWSER_WIDTH = 638
    BROWSER_HEIGHT = 823

CORE_DATA = {
    'asset': 'string',
    'balance': 'currency',
    'clock': 'time',
    'ema': 'float',
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
        'credentials': {
            'username': b'gAAAAABkpHCs67_ETDINvlZ4R_HcdrD9iI-t3RwKKbU9m_hg_YBrXH2SmDxSCD4_Pd1uxy3POAzzevoOw7KIxd3YWEfE0DSPKyngkbvg6ZAPI32uGZ7y344=',
            'password': b'gAAAAABkpHDCKUuyDm6wDy8f5-pLls9Clo-POfzmVfgBiJfdHk4O5wwf4hxJqDUZbkoigeMn8rhAwM7VPIX3qP-pd6l3N6oVxg=='
        },
        'neutral_zones': {
            'screen_center_25': {
                'width_pct': 0.50,
                'height_pct': 0.25
            },
            'bellow_app': {
                'width_pct': 0.50,
                'height_pct': 0.90
            },
            'within_app': {
                'width_pct': 0.50,
                'height_pct': 0.66
            },

        },
        'zones': {
            'header': {
                'id': 'header',
                'region': None,
                'locate_confidence': 0.88,
                'is_mandatory': True,
                'has_login_info': True,
                'elements': ['balance', 'asset']
            },
            'chart_top': {
                'id': 'chart_top',
                'region': None,
                'locate_confidence': 0.75,
                'is_mandatory': True,
                'elements': ['ohlc', 'ema', 'clock'],
            },
            'chart_bottom': {
                'id': 'chart_bottom',
                'region': None,
                'locate_confidence': 0.80,
                'is_mandatory': True,
                'elements': ['rsi']
            },
            'footer': {
                'id': 'footer',
                'region': None,
                'locate_confidence': 0.80,
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
            'ema_settings_tab1': {
                'context': 'tv',
                'id': 'ema_settings_tab1',
                'region': None,
                'locate_confidence': 0.50,
            },
            'ema_settings_tab2': {
                'context': 'tv',
                'id': 'ema_settings_tab2',
                'region': None,
                'locate_confidence': 0.50,
            },
            'rsi_settings_tab1': {
                'context': 'tv',
                'id': 'rsi_settings_tab1',
                'region': None,
                'locate_confidence': 0.50,
            },
            'rsi_settings_tab2': {
                'context': 'tv',
                'id': 'rsi_settings_tab2',
                'region': None,
                'locate_confidence': 0.50,
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
            'btn_super_strike': {
                'zone': 'footer',
                'x': None,
                'y': None
            },
            'btn_activate': {
                'context': 'iqcent',
                'zone': 'btn_activate',
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
            'input_chart_settings_scale_lines': {
                'context': 'tv',
                'zone': 'chart_settings_tab4_mid',
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
            'input_url': {
                'context': 'chrome',
                'zone': 'navbar_url',
                'x': None,
                'y': None
            },
            'navitem_ema_settings_tab1': {
                'context': 'tv',
                'zone': 'ema_settings_tab1',
                'x': None,
                'y': None
            },
            'navitem_ema_settings_tab2': {
                'context': 'tv',
                'zone': 'ema_settings_tab1',
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
                'zone': 'rsi_settings_tab2',
                'x': None,
                'y': None
            },
            'navitem_rsi_settings_tab2': {
                'context': 'tv',
                'zone': 'rsi_settings_tab2',
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
            'toggle_expiry_time': {
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
            'dp_item_5': {
                'context': 'tv',
                'zone': 'dp_item_5',
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
            'area_bottom_right_conner': {
                'context': 'tv',
                'zone': 'area_bottom_right_conner',
                'x': None,
                'y': None
            },

        }
    }
}
