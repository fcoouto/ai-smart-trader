from engine import settings, utils
from engine.Logger import Logger

from time import gmtime, strftime, sleep
from tabulate import tabulate
import art

import os
import pandas as pd
import pyautogui
import pytesseract
import random
import re

pyautogui.FAILSAFE = True
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

tmsg = utils.tmsg()
logger = Logger()


class SmartTrader:
    agent_id = None

    broker = None
    region = None
    mode = None
    session = {
        'token_refresh_time': None
    }

    balance = None
    initial_trade_size = None
    trade_size = None

    recovery_mode = None
    recovery_trade_size = 0.00
    cumulative_losses = 0.00
    consecutive_gains = 0

    expiry_time = None
    payout = None
    datetime = []

    asset = None
    open = []
    high = []
    low = []
    close = []
    change = []
    change_pct = []

    ema_72 = []
    rsi = []

    position_history = []

    ongoing_positions = {}
    # ongoing_positions = {
    #     'ema_rsi_8020': {'asset': 'ABC',
    #                      'strategy_id': 'ema_rsi_8020',
    #                      'open_time': 'XXX',
    #                      'open_price': 0.674804,
    #                      'side': 'down',
    #                      'result': None,
    #                      'trades': [{'open_time': 'XXX',
    #                                  'side': 'up',
    #                                  'trade_size': 1,
    #                                  'result': None}]
    #      }
    # }

    is_automation_running = False
    awareness = {
        'balance_equal_to_zero': None,
        'balance_less_than_min_balance': None,
        'payout_low': None,
    }

    def __init__(self, agent_id, broker, region, initial_trade_size):
        self.agent_id = agent_id
        self.broker = broker
        self.region = region
        self.initial_trade_size = initial_trade_size

        # self.execute_playbook(playbook_id='refresh_page')

        # HERE: Select top X asset based on payout X (region)

        # Setting zones
        self.set_zones()

        # Setting [trade_size]
        self.execute_playbook(playbook_id='set_trade_size', trade_size=initial_trade_size)

    def set_awareness(self, k, v):
        if k in self.awareness:
            self.awareness[k] = v
        else:
            # Key not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n\t- I couldn't find the key [{k}] within object [self.awareness]! :/"
                   f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            exit(500)

    ''' Validations '''

    def set_zones(self):
        for zone in self.broker['zones'].values():
            if 'is_mandatory' in zone and zone['is_mandatory']:
                # Setting zone regions
                zone['region'] = self.get_zone_region(context_id=self.broker['id'],
                                                      zone_id=zone['id'],
                                                      confidence=zone['locate_confidence'])

                # Defining element values
                for element_id in zone['elements']:
                    if 'elements' not in self.broker.keys():
                        self.broker['elements'] = {}
                    if element_id not in self.broker['elements'].keys():
                        self.broker['elements'][element_id] = {}

                    element_type = settings.CORE_DATA[element_id]
                    self.broker['elements'][element_id]['id'] = element_id
                    self.broker['elements'][element_id]['zone'] = zone['id']
                    self.broker['elements'][element_id]['type'] = element_type

                    self.read_element(element_id=element_id)

        # DEBUG
        # if settings.DEBUG_OCR:
        #     while True:
        #         asset = self.read_element(element_id='asset')
        #         balance = self.read_element(element_id='balance')
        #         payout = self.read_element(element_id='payout')
        #         chart_data = self.read_element(element_id='chart_data')
        #         trade_size = self.read_element(element_id='trade_size')
        #         expiry_time = self.read_element(element_id='expiry_time')
        #
        #         dst_price_ema_72 = utils.distance_percent(v1=chart_data[3], v2=chart_data[6])
        #
        #         print(f"{asset} | "
        #               f"{balance} | "
        #               f"{str(trade_size)} | "
        #               f"{payout} | "
        #               f"{expiry_time} | "
        #               f"{str(chart_data)}")
        #         print(f"{dst_price_ema_72}")

    def run_validation(self):
        # Run here the logic to validate screen. It pauses if human is needed
        #   . logged in?
        #   . balance?
        #   . expiry_time?
        #   . trade_size?
        #   . payout?

        context = 'Validation'

        # Validating readability of elements within the region (user logged in)
        self.set_zones()

        # Validating [balance]
        self.validate_balance(context=context)

        # Validating [trade_size]
        self.validate_trade_size(context=context)

        # Validating [expiry_time]
        self.validate_expiry_time()

        # Validating [payout]
        self.validate_payout()

    def validate_balance(self, context='Validation'):
        if self.balance == 0:
            if not self.awareness['balance_equal_to_zero']:
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc} "
                       f"{tmsg.italic}- Your current Balance is [{self.balance} USD]. "
                       f"So I think it makes sense to activate [{settings.MODE_SIMULATION}] mode, right? {tmsg.endc}")

                # Waiting PB
                msg = f"Activating {settings.MODE_SIMULATION} mode (CTRL + C to cancel)"
                wait_secs = settings.PROGRESS_BAR_WAITING_TIME
                items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                self.set_awareness(k='balance_equal_to_zero', v=True)
                self.mode = settings.MODE_SIMULATION

        elif self.balance < settings.MIN_BALANCE:
            if not self.awareness['balance_less_than_min_balance']:
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc} "
                       f"{tmsg.italic}- Your current Balance is [{self.balance} USD]. "
                       f"I would recommend at least [{settings.MIN_BALANCE} USD]. {tmsg.endc}")
                tmsg.print(context=context, msg=msg, clear=True)

                msg = f"{tmsg.italic}\n\t- Should I continue anyway? (CTRL-C to abort) {tmsg.endc}"
                tmsg.input(context=context, msg=msg)

                self.set_awareness(k='balance_less_than_min_balance', v=True)
                self.read_balance()

    def validate_trade_size(self, context='Validation'):
        optimal_trade_size = self.get_optimal_trade_size()

        if len(self.ongoing_positions) == 0 and self.trade_size != optimal_trade_size:
            # [trade_size] is different from [initial_trade_size]

            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Just noticed that Trade Size is [{self.trade_size} USD], "
                   f"and the Optimal Trade Size right now would be [{optimal_trade_size} USD]. "
                   f"\n\t  - I'll take care of that...{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Setting Trade Size (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            self.execute_playbook(playbook_id='set_trade_size', trade_size=optimal_trade_size)
            self.read_trade_size()

            print(f"{utils.tmsg.italic}\n\t  - Done! {utils.tmsg.endc}")
            sleep(1)

    def validate_expiry_time(self, context='Validation'):
        while self.expiry_time is not None and self.expiry_time != '01:00':
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Expiry Time is currently set to [{self.expiry_time}], "
                   f"but I'm more expirienced with [01:00]."
                   f"\n"
                   f"\n\t  - Let me try to change it. :){utils.tmsg.endc}")

            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Setting Expiry Time (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Executing playbook
            self.execute_playbook(playbook_id='set_expiry_time', expiry_time='01:00')
            self.read_expiry_time()

            if self.expiry_time == '01:00':
                print(f"{utils.tmsg.italic}\n\t- Done! {utils.tmsg.endc}")
                sleep(1)

    def validate_payout(self, context='Validation'):
        while self.payout < 75:
            if not self.awareness['payout_low']:
                msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                       f"{utils.tmsg.italic}- Payout is currently [{self.payout}%]. "
                       f"Maybe it's time to look for another asset? {utils.tmsg.endc}")
                tmsg.print(context=context, msg=msg, clear=True)

                msg = f"{utils.tmsg.italic}\n\t- Let me know when I can continue. (CTRL-C to abort) {utils.tmsg.endc}"
                tmsg.input(context=context, msg=msg)

                self.set_awareness(k='payout_low', v=True)

    def get_optimal_trade_size(self):
        optimal_trade_size = self.initial_trade_size
        min_position_loss = self.initial_trade_size + \
                            self.initial_trade_size * settings.MARTINGALE_MULTIPLIER + \
                            self.initial_trade_size * settings.MARTINGALE_MULTIPLIER * 2

        if self.cumulative_losses >= min_position_loss:
            # [cumulative_losses] is in a considerable size to be managed
            self.recovery_mode = True

            recovery_trade_size = self.cumulative_losses / settings.AMOUNT_TRADES_TO_RECOVER_LOSSES

            if self.recovery_trade_size > self.initial_trade_size:
                self.recovery_trade_size = recovery_trade_size
                optimal_trade_size = recovery_trade_size
        else:
            self.recovery_mode = False

        return round(optimal_trade_size, 2)

    def is_logged_in(self):
        return False if self.balance is None else True

    def is_alert_401_popping_up(self):
        zone_id = 'alert_401'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.90)
        if zone_region:
            # Zone [alert_401] has been found
            # Which means session has expired.
            return True

    ''' OCR '''

    def get_zone_region(self, context_id, zone_id, confidence=settings.LOCATE_CONFIDENCE):
        context = 'Validation'
        zone_region = None
        ss_template = self.get_ss_path(zone_id=zone_id,
                                       context_id=context_id)

        if zone_id not in self.broker['zones']:
            # Zone is NOT expected on broker's object
            zone_region = pyautogui.locateOnScreen(ss_template,
                                                   region=self.region,
                                                   confidence=confidence)

        else:
            # Zone is expected on broker's object
            while zone_region is None:
                zone = self.broker['zones'][zone_id]
                zone_region = pyautogui.locateOnScreen(ss_template,
                                                       region=self.region,
                                                       confidence=zone['locate_confidence'])

                if zone_region is None:
                    # Zone couldn't be located on screen
                    zone = self.broker['zones'][zone_id]

                    if 'has_login_info' in zone and zone['has_login_info']:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"- Seems like you are not logged in. "
                               f"\n\t- Or maybe your session window at [{self.broker['name']}] couldn't be found on the "
                               f"expected [monitor] and [region]."
                               f"\n\t- In any case, I'll try to log you in now...{utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        # # Waiting PB
                        msg = "Trying to remember the password (CTRL + C to cancel)"
                        wait_secs = settings.PROGRESS_BAR_WAITING_TIME
                        items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                        for item in utils.progress_bar(items, prefix=msg, reverse=True):
                            sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                        # Executing playbook
                        self.execute_playbook(playbook_id='log_in')

                        msg = f"\t- Done !"
                        tmsg.print(context=context, msg=msg)
                        sleep(1)

                    elif self.is_automation_running is False:
                        msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                               f"- I couldn't find zone_region for [{zone_id}]."
                               f"\n\t  - I see you are logged in [{self.broker['name']}] "
                               f"but seems like things are not quite in place yet."
                               f"\n"
                               f"\n\t  - Let me try to fix it and I'll get back to you soon..."
                               f"\n\t  - Ooh! I'll need Mouse and Keyboard control for a few seconds. Is that ok? :){utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        # Waiting PB
                        msg = "Gathering tools for Chart Setup (CTRL + C to cancel)"
                        wait_secs = settings.PROGRESS_BAR_WAITING_TIME
                        items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                        for item in utils.progress_bar(items, prefix=msg, reverse=True):
                            sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                        # Executing playbook
                        self.execute_playbook(playbook_id=f"{self.broker['id']}_chart_setup")

                        msg = f"\t- Done !"
                        tmsg.print(context=context, msg=msg)
                        sleep(1)

                    else:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"- I couldn't find zone_region for [{zone_id}]. "
                               f"\n\t- I see you are logged in just fine but things are not quite in place yet."
                               f"\n"
                               f"\n\t- For this one, I'll need some human support. :){utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        msg = f"{utils.tmsg.italic}\n\t- Should I try again? (enter){utils.tmsg.endc}"
                        tmsg.input(msg=msg)

        return zone_region

    def get_ss_path(self, zone_id, context_id=None, element_id=None, template=True):
        if context_id is None:
            context_id = self.broker['id']

        if template:
            return f"{settings.PATH_SS_TEMPLATE}" \
                   f"{context_id}__{zone_id}{settings.SS_FILE_EXTENSION}"

        else:
            return f"{settings.PATH_SS}" \
                   f"{context_id}__{zone_id}__{element_id}{settings.SS_FILE_EXTENSION}"

    def screenshot_element(self, zone_id, element_id, save_to=None):
        zone = self.broker['zones'][zone_id]

        img = pyautogui.screenshot(region=zone['region'])
        img = self.crop_screenshot(img=img,
                                   zone_id=zone_id,
                                   element_id=element_id)

        if save_to:
            img.save(save_to)

        return img

    def crop_screenshot(self, img, zone_id, element_id):
        width, height = img.size

        left = top = 0
        right = width
        bottom = height

        if self.broker['id'] == 'iqcent':
            if zone_id == 'header':
                if element_id == 'asset':
                    left = width * 0.07
                    top = height * 0.17
                    right = width * 0.40
                    bottom = height * 0.35
                elif element_id == 'balance':
                    left = width * 0.50
                    top = height * 0.17
                    right = width * 0.80
                    bottom = height * 0.35
            elif zone_id == 'chart_top':
                if element_id == 'ohlc':
                    left = width * 0.143
                    top = height * 0.70
                    right = width
                    bottom = height * 0.83
                elif element_id == 'ema_72':
                    left = width * 0.45
                    top = height * 0.85
                    right = width * 0.66
                    bottom = height
            elif zone_id == 'chart_bottom':
                if element_id == 'rsi':
                    left = width * 0.58
                    top = height * 0.03
                    right = width
                    bottom = height * 0.23
            elif zone_id == 'footer':
                if element_id == 'trade_size':
                    left = width * 0.15
                    top = height * 0.44
                    right = width * 0.35
                    bottom = height * 0.61
                if element_id == 'close':
                    left = width * 0.38
                    top = height * 0.77
                    right = width * 0.63
                    bottom = height
                elif element_id == 'expiry_time':
                    left = width * 0.70
                    top = height * 0.33
                    right = width * 0.82
                    bottom = height * 0.48
                elif element_id == 'payout':
                    left = width * 0.05
                    top = height * 0.79
                    right = width * 0.28
                    bottom = height * 0.97

        img = img.crop([left, top, right, bottom])
        return img

    def ocr_read_element(self, zone_id, element_id, context_id=None, type='string'):
        # There will be 3 attempts to read the content.

        for attempt in range(1, 3):
            ss_path = None
            if settings.DEBUG_OCR:
                ss_path = self.get_ss_path(zone_id=zone_id,
                                           context_id=context_id,
                                           element_id=element_id,
                                           template=False)

            img = self.screenshot_element(zone_id=zone_id,
                                          element_id=element_id,
                                          save_to=ss_path)

            if type == 'float':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789.'
            elif type == 'string':
                config = '--psm 7 -c tessedit_char_whitelist="/ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "'
            elif type == 'string_ohlc':
                config = '--psm 7 -c tessedit_char_whitelist="OHLC0123456789. "'
            elif type == 'currency':
                config = '--psm 7 -c tessedit_char_whitelist="0123456789. ABCDEFGHIJKLMNOPQRSTUVWXYZ"'
            elif type == 'int':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789'
            elif type == 'time':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789:'
            elif type == 'percentage':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789.%'
            else:
                config = ''

            text = pytesseract.image_to_string(image=img, config=config)
            text = text.strip()

            if text:
                return text

    def read_element(self, element_id):
        # Error handler wrapper of each [read_{element_id}] function
        result = None
        tries = 0
        is_processed = None

        f_read = f"read_{element_id}"
        if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
            while not is_processed:
                tries += 1

                try:
                    result = read()
                    is_processed = True
                except Exception as err:
                    if tries >= settings.MAX_TRIES_READING_ELEMENT:
                        # Something is going on here... Refresh page
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"- That's weird... While reading [{element_id}], I noticed this:"
                               f"\n"
                               f"\n\t{type(err)}: {err}"
                               f"\n"
                               f"\n- The reasons for that can vary, but here are my thoughts:"
                               f"\n\t  . Authorization expired."
                               f"\n\t  . Broker facing performance issues."
                               f"\n\t  . Unstable internet connection."
                               f"\n"
                               f"\n- I think I should try to refresh the page and see if it is still up... {utils.tmsg.endc}")
                        tmsg.print(msg=msg, clear=True)

                        # Waiting PB
                        msg = "Refreshing Page (CTRL + C to cancel)"
                        wait_secs = settings.PROGRESS_BAR_WAITING_TIME
                        items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                        for item in utils.progress_bar(items, prefix=msg, reverse=True):
                            sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                        # Executing playbook
                        self.execute_playbook(playbook_id='refresh_page')
                        self.run_validation()

                        result = read()
        else:
            # Function not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n- I couldn't find function [{f_read}]!"
                   f"\n- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            exit(500)

        return result

    def read_asset(self):
        element_id = 'asset'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        value = re.sub("[^A-z/ ]", "", value)

        if self.asset is None:
            self.asset = value

        elif self.asset != value:
            # Asset has changed

            asset = str(self.asset).replace('/', '-').replace(' ', '_')
            url = self.broker['url']
            url += asset

            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- hmm... Just noticed [asset] changed from [{self.asset}] to [{asset}]."
                   f"\n\t  - I'll open [{self.asset}] again, so we can continue on the same asset."
                   f"\n\t  - If you want to change it, please restart me.{utils.tmsg.endc}")
            tmsg.print(msg=msg, clear=True)

            # Waiting PB
            msg = "Loading page (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            self.execute_playbook(playbook_id='navigate_url', url=url)

            self.reset_chart_data()
            self.set_awareness(k='payout_low', v=True)

        # Renaming PowerShell window name
        os.system(f'title STrader: {value}')

        return self.asset

    def read_balance(self):
        element_id = 'balance'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        missing_decimal_separator = True if '.' not in value else False
        value = utils.str_to_float(value)

        if missing_decimal_separator:
            # It's expected that [trade_size] field will always have 2 decimals
            value = value / 100

        self.balance = value
        return self.balance

    def read_trade_size(self):
        element_id = 'trade_size'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        missing_decimal_separator = True if '.' not in value else False
        value = utils.str_to_float(value)

        if missing_decimal_separator:
            # It's expected that [trade_size] field will always have 2 decimals
            value = value / 100

        self.trade_size = value

        return self.trade_size

    def read_chart_data(self):
        # todo: Execute concurrent processes
        o, h, l, c, change, change_pct = self.read_ohlc()
        # close = self.read_close()
        ema_72 = self.read_ema_72()
        rsi = self.read_rsi()

        tm_sec = gmtime().tm_sec
        if tm_sec >= 58 or tm_sec <= 1:
            self.datetime.insert(0, strftime("%Y-%m-%d %H:%M:%S", gmtime()))

            self.open.insert(0, o)
            self.high.insert(0, h)
            self.low.insert(0, l)
            self.close.insert(0, c)

            self.change.insert(0, change)
            self.change_pct.insert(0, change_pct)

            self.ema_72.insert(0, ema_72)
            self.rsi.insert(0, rsi)

        return [o, h, l, c, change, change_pct, ema_72, rsi]

    def reset_chart_data(self):
        self.datetime.clear()
        self.open.clear()
        self.high.clear()
        self.low.clear()
        self.close.clear()
        self.change.clear()
        self.change_pct.clear()

        self.ema_72.clear()
        self.rsi.clear()

    def read_close(self):
        element_id = 'close'

        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    def read_ohlc(self):
        # Returns [open, high, low, close, change]
        element_id = 'ohlc'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        # Replacing any letter [O] by number [0]
        ohlc = value.replace('O', '0')

        if ohlc[:2] == '0.':
            # If first [O] wasn't recognized, add it
            ohlc = '0' + ohlc

        o, h, l, c = ohlc.split(' ')
        o = utils.str_to_float(o[1:])
        h = utils.str_to_float(h[1:])
        l = utils.str_to_float(l[1:])
        c = utils.str_to_float(c[1:])
        change = utils.str_to_float("%.6f" % (c - o))
        change_pct = utils.distance_percent(v1=c, v2=o)

        return [o, h, l, c, change, change_pct]

    def read_ema_72(self):
        element_id = 'ema_72'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    def read_rsi(self):
        element_id = 'rsi'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    def read_expiry_time(self):
        element_id = 'expiry_time'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        self.expiry_time = value
        return self.expiry_time

    def read_payout(self):
        element_id = 'payout'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = re.sub("[^0-9]", "", value)

        self.payout = int(value)
        return self.payout

    def read_alert_401(self):
        element_id = 'alert_401'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        return value

    ''' Mouse & Keyboard '''

    def get_element(self, element_id):
        if element_id in self.broker['elements']:
            element = self.broker['elements'][element_id]
        else:
            element = {'zone': None,
                       'x': None,
                       'y': None}

        if 'context' in element:
            # Used to read the dependency zone file (tv__menu_chart.png).
            context_id = element['context']
        else:
            context_id = self.broker['id']

        # references
        region = self.region

        zone_region = self.get_zone_region(context_id=context_id,
                                           zone_id=element['zone'])
        zone_center_x = zone_region.left + zone_region.width / 2
        zone_center_y = zone_region.top + zone_region.height / 2

        if element_id == 'browser_url':
            element['x'] = region['center_x']
            element['y'] = 60

        elif self.broker['id'] == 'iqcent':
            if element_id == 'area_chart_background':
                element['x'] = region['center_x']
                element['y'] = zone_region.top
            elif element_id == 'btn_login':
                element['x'] = zone_region.left + 490
                element['y'] = zone_region.top + 35
            elif element_id == 'btn_login_confirm':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 285
            elif element_id == 'btn_chart_type_candle':
                element['x'] = zone_region.left + 62
                element['y'] = zone_region.top + 90
            elif element_id == 'btn_chart_timeframe':
                element['x'] = zone_region.left + 240
                element['y'] = zone_region.top + 20
            elif element_id == 'btn_chart_indicators':
                element['x'] = zone_region.left + 410
                element['y'] = zone_region.top + 90
            elif element_id == 'btn_ema_settings':
                element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 135
            elif element_id == 'btn_rsi_settings':
                element['x'] = zone_region.left + 170
                element['y'] = zone_region.top + 225
            elif element_id == 'btn_chart_remove_indicators':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 145
            elif element_id == 'btn_chart_settings':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 235
            elif element_id == 'btn_expiry_time':
                element['x'] = zone_region.left + 460
                element['y'] = zone_region.top + 75
            elif element_id == 'btn_call':
                element['x'] = zone_region.left + 100
                element['y'] = zone_region.top + 125
            elif element_id == 'btn_put':
                element['x'] = zone_region.left + 510
                element['y'] = zone_region.top + 125
            elif element_id == 'checkbox_chart_settings_bar_change_values':
                element['x'] = zone_region.left + 80
                element['y'] = zone_region.top + 245
            elif element_id == 'checkbox_rsi_settings_upper_limit':
                element['x'] = zone_region.left + 30
                element['y'] = zone_region.top + 175
            elif element_id == 'checkbox_rsi_settings_lower_limit':
                element['x'] = zone_region.left + 30
                element['y'] = zone_region.top + 225
            elif element_id == 'checkbox_rsi_settings_hlines_bg':
                element['x'] = zone_region.left + 30
                element['y'] = zone_region.top + 280
            elif element_id == 'item_color_white':
                element['x'] = zone_region.left + 20
                element['y'] = zone_region.top + 25
            elif element_id == 'input_email':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 65
            elif element_id == 'input_pwd':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 120
            elif element_id == 'input_color_opacity':
                element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + zone_region.height
            elif element_id == 'input_chart_settings_body_green':
                element['x'] = zone_region.left + 225
                element['y'] = zone_region.top + 145
            elif element_id == 'input_chart_settings_body_red':
                element['x'] = zone_region.left + 270
                element['y'] = zone_region.top + 145
            elif element_id == 'input_chart_settings_wick_green':
                element['x'] = zone_region.left + 225
                element['y'] = zone_region.top + 245
            elif element_id == 'input_chart_settings_wick_red':
                element['x'] = zone_region.left + 270
                element['y'] = zone_region.top + 245
            elif element_id == 'input_ema_settings_color':
                element['x'] = zone_region.left + 140
                element['y'] = zone_region.top + 130
            elif element_id == 'input_ema_settings_length':
                element['x'] = zone_region.left + 130
                element['y'] = zone_region.top + 130
            elif element_id == 'input_ema_settings_precision':
                element['x'] = zone_region.left + 140
                element['y'] = zone_region.top + 180
            elif element_id == 'input_rsi_settings_color':
                element['x'] = zone_region.left + 220
                element['y'] = zone_region.top + 130
            elif element_id == 'input_rsi_settings_length':
                element['x'] = zone_region.left + 130
                element['y'] = zone_region.top + 130
            elif element_id == 'input_url':
                element['x'] = zone_region.left + zone_region.width + 50
                element['y'] = zone_center_y
            elif element_id == 'slider_background_opacity':
                element['x'] = zone_region.left + 260
                element['y'] = zone_region.top + 200
            elif element_id == 'navitem_chart_settings_tab1':
                element['x'] = zone_region.left + 25
                element['y'] = zone_region.top + 80
            elif element_id == 'navitem_chart_settings_tab2':
                element['x'] = zone_region.left + 25
                element['y'] = zone_region.top + 120
            elif element_id == 'navitem_ema_settings_tab1':
                element['x'] = zone_region.left + 40
                element['y'] = zone_region.top + 65
            elif element_id == 'navitem_ema_settings_tab2':
                element['x'] = zone_region.left + 110
                element['y'] = zone_region.top + 65
            elif element_id == 'navitem_rsi_settings_tab1':
                element['x'] = zone_region.left + 40
                element['y'] = zone_region.top + 65
            elif element_id == 'navitem_rsi_settings_tab2':
                element['x'] = zone_region.left + 110
                element['y'] = zone_region.top + 65
            elif element_id == 'trade_size':
                element['x'] = zone_region.left + 150
                element['y'] = zone_region.top + 75
            elif element_id == 'dp_item_1min':
                element['x'] = zone_center_x
                element['y'] = zone_center_y
            elif element_id == 'dp_item_6':
                element['x'] = zone_center_x
                element['y'] = zone_center_y

        return element

    def mouse_event_on_neutral_area(self, event='click', area_id='bellow_app'):
        # Clicking on target monitor

        if area_id in self.broker['neutral_zones']:
            x = self.region['x'] + self.region['width'] * self.broker['neutral_zones'][area_id]['width_pct']
            y = self.region['y'] + self.region['height'] * self.broker['neutral_zones'][area_id]['height_pct']
        else:
            # Key not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n\t- I couldn't find area [{area_id}] within object [self.broker.neutral_zones]! :/"
                   f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            exit(500)

        if event == 'click':
            pyautogui.click(x=x, y=y)
        else:
            pyautogui.moveTo(x=x, y=y)

    def click_element(self, element_id, clicks=1, button='left', duration=0.0, wait_when_done=0.0):
        element = self.get_element(element_id=element_id)
        pyautogui.click(x=element['x'],
                        y=element['y'],
                        clicks=clicks,
                        button=button,
                        duration=duration)

        # After click, wait the same amount of time used for [duration].
        # It gives time for CSS to load and transformations.
        # if [duration] is, we understand it's urgent and there can't be any wait time.
        sleep(wait_when_done)

    def move_to_element(self, element_id, duration=0.0):
        element = self.get_element(element_id=element_id)
        pyautogui.moveTo(x=element['x'],
                         y=element['y'],
                         duration=duration)

    ''' Playbooks '''

    def execute_playbook(self, playbook_id, **kwargs):
        self.is_automation_running = True
        result = None

        # Looking for playbook
        f_playbook = f"playbook_{playbook_id}"
        if hasattr(self, f_playbook) and callable(playbook := getattr(self, f_playbook)):
            # Playbook has been found
            if playbook_id in settings.PLAYBOOK_LONG_ACTION:
                # It's a long action

                lock_file = f"{settings.PATH_LOCK}{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}"
                is_done = False
                amount_tries = 0

                while is_done is False:
                    try:
                        # Locking it while doing stuff
                        with open(file=lock_file, mode='x') as f:
                            f.write(playbook_id)
                            f.flush()

                            result = playbook(**kwargs)
                            is_done = True

                    except FileExistsError:
                        # This long action is waiting for another one
                        # It likely means authentication token expired. So refresh_page on the next opportunity
                        with open(file=lock_file, mode='r') as f:
                            playbook_id_running = f.read()

                        if playbook_id_running == playbook_id == 'log_in':
                            # The other instance is logging in.
                            # So, refreshing this one
                            playbook = getattr(self, 'playbook_refresh_page')

                        sleep(1)
                        amount_tries += 1

                        if amount_tries > settings.PLAYBOOK_LONG_ACTION[playbook_id_running] * 3:
                            # It's taking way too long

                            result = playbook(**kwargs)
                            is_done = True

                    finally:
                        try:
                            os.remove(lock_file)
                        except:
                            pass

            else:
                # It's not a long action
                result = playbook(**kwargs)

        else:
            # Playbook not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n\t- I couldn't find the playbook [{playbook_id}]! :/"
                   f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            exit(500)

        # Clicking on Neutral Area
        self.mouse_event_on_neutral_area(event='click', area_id='bellow_app')

        self.is_automation_running = False
        return result

    def playbook_log_in(self):
        self.click_element(element_id='btn_login', wait_when_done=0.500)

        # Filling up credentials
        self.click_element(element_id='input_email')
        pyautogui.typewrite('f.couto@live.com', interval=0.05)
        pyautogui.press('tab')
        pyautogui.typewrite('#F1807a$Iqcent', interval=0.05)

        # Confirming login
        self.click_element(element_id='btn_login_confirm', wait_when_done=0.250)

        # Waiting for authentication
        sleep(5)

    def playbook_refresh_page(self):
        pyautogui.click(x=self.region['center_x'], y=self.region['center_y'])
        pyautogui.hotkey('shift', 'f5')

        # Resetting some awareness attributes
        self.set_awareness('payout_low', False)

        # Waiting for page to load
        sleep(5)

    def playbook_navigate_url(self, url=None):
        # Cleaning field
        self.click_element(element_id='input_url')
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')

        # Typing new URL
        pyautogui.typewrite(url, interval=0.05)

        # Go
        pyautogui.press('enter')

        # Waiting for page to load
        sleep(5)

    def playbook_tv_reset(self):
        # Reseting chart
        self.click_element(element_id='area_chart_background', duration=0.400)
        pyautogui.hotkey('alt', 'r')

        # Removing all indicators
        self.playbook_tv_remove_all_indicators()

    def playbook_tv_remove_all_indicators(self):
        self.click_element(element_id='area_chart_background', button='right', duration=0.400)
        self.click_element(element_id='btn_chart_remove_indicators', duration=0.300)

        # If there are no indicators on the chart, just close dropdown-menu
        pyautogui.press('escape')

    def playbook_iqcent_chart_setup(self):
        # Refreshing page
        self.playbook_refresh_page()

        # Chart Type
        self.click_element(element_id='btn_chart_type_candle', wait_when_done=5.00)

        # Defining Chart Settings
        self.playbook_tv_set_chart_settings()

        # Clicking on Neutral Area
        self.mouse_event_on_neutral_area(event='click', area_id='bellow_app')

        # Defining EMA 72 up
        self.playbook_tv_add_indicator(hint='Moving Average Exponential')
        self.playbok_tv_configure_indicator_ema(length=72)

        # Clicking on Neutral Area
        self.mouse_event_on_neutral_area(event='click', area_id='bellow_app')

        # Defining RSI
        self.playbook_tv_add_indicator(hint='Relative Strength Index')
        self.playbok_tv_configure_indicator_rsi(length=3)

    def playbook_tv_set_chart_settings(self, candle_opacity=5):
        # Opening Chart Settings
        self.click_element(element_id='area_chart_background', button='right', wait_when_done=0.250)
        self.click_element(element_id='btn_chart_settings', wait_when_done=0.300)

        # Opening Tab 1
        self.click_element(element_id='navitem_chart_settings_tab1', wait_when_done=0.250)

        # [tab1] Configuring [candle_body] opacity
        self.click_element(element_id='input_chart_settings_body_green', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        self.click_element(element_id='input_chart_settings_body_red', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        # [tab1] Configuring [candle_wick] opacity
        self.click_element(element_id='input_chart_settings_wick_green', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        self.click_element(element_id='input_chart_settings_wick_red', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        # Opening Tab 2
        self.click_element(element_id='navitem_chart_settings_tab2', wait_when_done=0.250)

        # [tab2] Toggling [Bar Change Values]
        self.click_element(element_id='checkbox_chart_settings_bar_change_values')

        # [tab2] Scrolling down
        pyautogui.scroll(-500)
        sleep(0.250)

        # [tab2] Dragging [slider_background_opacity] handler to 100%
        self.move_to_element(element_id='slider_background_opacity')
        pyautogui.drag(xOffset=75, duration=0.200)

        # Exiting Chart Settings
        pyautogui.press('escape')

    def playbook_tv_add_indicator(self, hint):
        # Opening [btn_chart_indicators] element
        self.click_element(element_id='btn_chart_indicators', wait_when_done=0.300)

        # Adding indicator
        pyautogui.typewrite(hint, interval=0.05)
        pyautogui.press('down')
        pyautogui.press('enter')
        pyautogui.press('escape')

    def playbok_tv_configure_indicator_ema(self, length, color='white', opacity=5, precision=6):
        # Opening Settings
        self.click_element(element_id='btn_ema_settings', wait_when_done=0.300)

        # [tab1]
        self.click_element(element_id='navitem_ema_settings_tab1', wait_when_done=0.250)

        # [tab1] Setting [length]
        self.click_element(element_id='input_ema_settings_length', clicks=2)
        pyautogui.typewrite(str(length))

        # [tab2]
        self.click_element(element_id='navitem_ema_settings_tab2', wait_when_done=0.250)

        # [tab2] Setting [color]
        self.click_element(element_id='input_ema_settings_color', wait_when_done=0.250)
        self.click_element(element_id=f'item_color_{color}')
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')

        # [tab2] Setting [precision]
        self.click_element(element_id='input_ema_settings_precision', wait_when_done=0.250)
        self.click_element(element_id=f'dp_item_{precision}')

        # Leaving Settings and Selection
        pyautogui.press(['escape', 'escape'], interval=0.100)

    def playbok_tv_configure_indicator_rsi(self, length, color='white', opacity=5):
        # Opening Settings
        self.click_element(element_id='btn_rsi_settings', wait_when_done=0.300)

        # [tab1]
        self.click_element(element_id='navitem_rsi_settings_tab1', wait_when_done=0.250)

        # [tab1] Setting [length]
        self.click_element(element_id='input_rsi_settings_length', clicks=2)
        pyautogui.typewrite(str(length))

        # [tab2]
        self.click_element(element_id='navitem_rsi_settings_tab2', wait_when_done=0.250)

        # [tab2] Setting [color]
        self.click_element(element_id='input_rsi_settings_color', wait_when_done=0.250)
        self.click_element(element_id=f'item_color_{color}')
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')

        # [tab2] Toggle [upper_limit]
        self.click_element(element_id='checkbox_rsi_settings_upper_limit')

        # [tab2] Toggle [lower_limit]
        self.click_element(element_id='checkbox_rsi_settings_lower_limit')

        # [tab2] Toggle [hlines_bg]
        self.click_element(element_id='checkbox_rsi_settings_hlines_bg')

        # Leaving Settings and Selection
        pyautogui.press(['escape', 'escape'], interval=0.100)

    def playbook_set_trade_size(self, trade_size):
        if self.trade_size != trade_size:
            self.click_element(element_id='trade_size', clicks=2)
            pyautogui.typewrite("%.2f" % trade_size)

    def playbook_set_expiry_time(self, expiry_time='01:00'):
        self.click_element(element_id='btn_expiry_time', wait_when_done=0.5)

        if expiry_time == '01:00':
            self.click_element(element_id='dp_item_1min')
        else:
            # Option is not supported. Closing dropdown menu
            pyautogui.press('escape')

    def playbook_open_trade(self, side, trade_size):
        self.playbook_set_trade_size(trade_size=trade_size)

        if side.lower() == 'up':
            self.click_element(element_id='btn_call')
        elif side.lower() == 'down':
            self.click_element(element_id='btn_put')

    ''' Reporting'''

    def df_ongoing_positions(self):
        rows = []
        columns = ['Strategy', 'Open Time (UTC)', 'Side', 'Size', 'Open Price']

        for position in self.ongoing_positions.values():
            row = [position['strategy_id'],
                   position['open_time'],
                   position['side'],
                   position['trades'][0]['trade_size'],
                   position['open_price']]

            i = 1
            for trade in position['trades']:
                if trade['result']:
                    value = trade['result']
                else:
                    value = 'on going'

                if 'Trade ' + str(i) not in columns:
                    columns.append('Trade ' + str(i))
                row.append(value)

                i += 1

            rows.append(row)

        print('columns:' + str(columns))
        print('rows:' + str(rows))

        df = pd.DataFrame(data=rows, columns=columns)
        df.fillna('', inplace=True)

        return df

    ''' TA & Trading '''

    def open_position(self, strategy_id, side, trade_size):
        position = {'result': None}

        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        position['asset'] = self.asset
        position['strategy_id'] = strategy_id
        position['open_time'] = now
        position['open_price'] = self.close[0]
        position['side'] = side
        position['trades'] = []

        self.ongoing_positions[strategy_id] = position
        self.open_trade(strategy_id=strategy_id, side=side, trade_size=trade_size)

        msg = f"[{self.asset}] Trade has been opened."
        logger.live(msg=msg)

        return position

    def close_position(self, strategy_id, result):
        self.close_trade(strategy_id=strategy_id, result=result)
        self.ongoing_positions[strategy_id]['result'] = result
        closed_position = self.ongoing_positions[strategy_id].copy()

        self.df_ongoing_positions().to_csv('data\\positions.csv', mode='a', index=False, header=False)

        self.position_history.append(self.ongoing_positions[strategy_id].copy())
        self.ongoing_positions.pop(strategy_id)

        # Setting [trade_size] back to [optimal_trade_size]
        self.read_balance()

        if (not os.path.exists(
                f"{settings.PATH_LOCK}{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}")
                or not self.ongoing_positions):
            self.execute_playbook(playbook_id='set_trade_size', trade_size=self.get_optimal_trade_size())

        return closed_position

    def open_trade(self, strategy_id, side, trade_size):
        self.execute_playbook(playbook_id='open_trade', side=side, trade_size=trade_size)

        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        trade = {
            'open_time': now,
            'side': self.ongoing_positions[strategy_id]['side'],
            'trade_size': trade_size,
            'result': None
        }

        self.ongoing_positions[strategy_id]['trades'].append(trade)
        return trade

    def close_trade(self, strategy_id, result):
        position = self.ongoing_positions[strategy_id]
        trade = position['trades'][-1]
        trade['result'] = result

        # Loss Management
        if result == 'gain':
            self.consecutive_gains += 1

            if self.cumulative_losses > 0:
                profit = trade['trade_size'] * (self.payout / 100)

                # Reducing [cumulative_losses]
                if self.cumulative_losses > profit:
                    # [cumulative_losses] is greater than [profit]
                    self.cumulative_losses -= profit
                else:
                    # Reseting [cumulative_losses]
                    self.cumulative_losses = 0

        elif result == 'loss':
            self.consecutive_gains = 0

            # Accumulating losses
            self.cumulative_losses += trade['trade_size']

        return position['trades'][-1]

    def start(self):
        msg = "Validating\n"
        tmsg.print(context='Warming Up!',
                   msg=msg,
                   clear=True)

        self.run_validation()
        sec_action = random.randrange(start=58250, stop=58750) / 1000

        while True:
            context = 'Trading' if self.ongoing_positions else 'Getting Ready!'
            tmsg.print(context=context, clear=True)

            if self.ongoing_positions:
                # Printing [ongoing_positions]

                tb_positions = self.df_ongoing_positions()
                tb_positions = tabulate(tb_positions, headers='keys', showindex=False)
                print(f"{tb_positions}\n\n")

            sec_validation = random.randrange(start=40000, stop=48000) / 1000

            # Waiting PB
            msg = "Watching Price Action"
            if sec_validation > gmtime().tm_sec:
                diff_sec = sec_validation - gmtime().tm_sec
            else:
                diff_sec = sec_validation - gmtime().tm_sec + 60

            items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Checking token (only if mouse/keyboard are not being used)
            if utils.does_lock_file_exist(lock_file='long_action') is False and len(self.ongoing_positions) == 0:
                # Focusing on App
                self.mouse_event_on_neutral_area(event='click', area_id='within_app')
                sleep(1)
                if self.is_alert_401_popping_up():
                    # 401 alert popping up
                    # Session has expired
                    self.execute_playbook(playbook_id='refresh_page')

            # Validation PB
            msg = "Quick validation"
            for item in utils.progress_bar([0], prefix=msg):
                self.run_validation()

            if gmtime().tm_sec >= sec_validation:
                # Ready for Trading

                # Waiting PB
                msg = "Watching candle closure"
                diff_sec = sec_action - gmtime().tm_sec

                items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                self.run_lookup(context=context)

            else:
                # Missed candle data (too late)
                msg = f"{tmsg.warning}We got late and missed last candle's data. \n" \
                      f"Because of that, it's wise to reset chart data.\n\n" \
                      f"But that's no big deal, no actions are needed on your side.{tmsg.endc}"
                tmsg.print(context=context,
                           msg=msg,
                           clear=True)

                # Cleaning up
                self.reset_chart_data()
                self.ongoing_positions.clear()

                wait_time = 5
                sleep(wait_time)

    def run_lookup(self, context):
        position = None
        # Strategies
        msg = "Applying strategies"
        strategies = []

        # Retrieving [strategies]
        # if self.ongoing_positions:
        #     # There is a position open
        #     # Making sure the current strategy is on the top
        #
        #     strategies.append(list(self.ongoing_positions.keys())[0])
        #
        #     for strategy in settings.TRADING_STRATEGIES:
        #         if strategy not in strategies:
        #             strategies.append(strategy)
        # else:
        #     # No positions open
        #     # Following the given sequence
        #     strategies = settings.TRADING_STRATEGIES.copy()
        strategies = settings.TRADING_STRATEGIES.copy()

        # Reading Chart data
        self.read_element(element_id='chart_data')

        # Looking up
        for strategy in utils.progress_bar(strategies, prefix=msg):
            # Strategies
            f_strategy = f"strategy_{strategy}"
            if hasattr(self, f_strategy) and callable(strategy := getattr(self, f_strategy)):
                position = strategy()
            else:
                # Strategy not found
                msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                       f"- That's embarrassing. :/ "
                       f"\n\t- I couldn't find a function for strategy [{strategy}].! :/"
                       f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
                tmsg.input(msg=msg, clear=True)
                exit(500)

            if position:
                tmsg.print(context=context, clear=True)

                if position['result']:
                    art.tprint(text=position['result'], font='block')
                    sleep(10)

                # Position found with this [strategy] and it's still in progress.
                # So skipping next ones.
                # break
        return position

    def strategy_ema_rsi_8020(self):
        strategy_id = 'ema_rsi_8020'

        if strategy_id in self.ongoing_positions:
            position = self.ongoing_positions[strategy_id]
        else:
            position = None

        if position:
            # Has position open
            result = None
            last_trade = position['trades'][-1]
            amount_trades = len(position['trades'])

            if position['side'] == 'up':
                # up
                if self.close[0] > position['open_price']:
                    result = 'gain'
                elif self.close[0] < position['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.close[0] < position['open_price']:
                    result = 'gain'
                elif self.close[0] > position['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            if result == 'gain':
                position = self.close_position(strategy_id=strategy_id,
                                               result=result)
            elif result == 'loss':
                if amount_trades >= settings.MAX_TRADES_PER_POSITION:
                    # No more tries
                    position = self.close_position(strategy_id=strategy_id,
                                                   result=result)

                elif position['side'] == 'up' and self.rsi[0] < 20:
                    # Abort it
                    position = self.close_position(strategy_id=strategy_id,
                                                   result=result)
                elif position['side'] == 'down' and self.rsi[0] > 80:
                    # Abort it
                    position = self.close_position(strategy_id=strategy_id,
                                                   result=result)

                if not position['result']:
                    # Martingale
                    if self.recovery_mode:
                        trade_size = self.get_optimal_trade_size()
                    else:
                        trade_size = last_trade['trade_size'] * settings.MARTINGALE_MULTIPLIER

                    self.close_trade(strategy_id=strategy_id,
                                     result=result)
                    self.open_trade(strategy_id=strategy_id,
                                    side=position['side'],
                                    trade_size=trade_size)
            else:
                # Draw
                self.close_trade(strategy_id=strategy_id,
                                 result=result)
                self.open_trade(strategy_id=strategy_id,
                                side=position['side'],
                                trade_size=last_trade['trade_size'])

        else:
            # No open position
            dst_price_ema_72 = utils.distance_percent_abs(v1=self.close[0], v2=self.ema_72[0])

            if len(self.datetime) >= 2:

                if self.close[0] > self.ema_72[0] or dst_price_ema_72 < -0.0005:
                    # Price is above [ema_72] or far bellow [ema_72]

                    if self.rsi[1] <= 20 and 30 <= self.rsi[0] <= 70:
                        position = self.open_position(strategy_id=strategy_id,
                                                      side='up',
                                                      trade_size=self.get_optimal_trade_size())

                elif self.close[0] < self.ema_72[0] or dst_price_ema_72 > 0.0005:
                    # Price is bellow [ema_72] or far above [ema_72]
                    if self.rsi[1] >= 80 and 70 >= self.rsi[0] >= 30:
                        # Trend Following
                        position = self.open_position(strategy_id=strategy_id,
                                                      side='down',
                                                      trade_size=self.get_optimal_trade_size())

        return position

    def strategy_ema_rsi_50(self):
        strategy_id = 'ema_rsi_50'

        if strategy_id in self.ongoing_positions:
            position = self.ongoing_positions[strategy_id]
        else:
            position = None

        if position:
            # Has position open
            result = None
            last_trade = position['trades'][-1]
            amount_trades = len(position['trades'])

            if position['side'] == 'up':
                # up
                if self.close[0] > position['open_price']:
                    result = 'gain'
                elif self.close[0] < position['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.close[0] < position['open_price']:
                    result = 'gain'
                elif self.close[0] > position['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            # Checking [result]
            if result == 'gain':
                position = self.close_position(strategy_id=strategy_id,
                                               result=result)
            elif result == 'loss':
                if amount_trades >= settings.MAX_TRADES_PER_POSITION:
                    # No more tries
                    position = self.close_position(strategy_id=strategy_id,
                                                   result=result)

                elif position['side'] == 'up':
                    if self.rsi[0] < 38:
                        # Abort it
                        position = self.close_position(strategy_id=strategy_id,
                                                       result=result)
                    elif self.close[1] > self.ema_72[1] and self.close[0] < self.ema_72[0]:
                        # [close] crossed [ema_72] up
                        # Abort it
                        position = self.close_position(strategy_id=strategy_id,
                                                       result=result)
                elif position['side'] == 'down':
                    if self.rsi[0] > 62:
                        # Abort it
                        position = self.close_position(strategy_id=strategy_id,
                                                       result=result)
                    elif self.close[1] < self.ema_72[1] and self.close[0] > self.ema_72[0]:
                        # [close] crossed [ema_72] down
                        # Abort it
                        position = self.close_position(strategy_id=strategy_id,
                                                       result=result)

                if not position['result']:
                    # Martingale
                    if self.recovery_mode:
                        trade_size = self.get_optimal_trade_size()
                    else:
                        trade_size = last_trade['trade_size'] * settings.MARTINGALE_MULTIPLIER

                    self.close_trade(strategy_id=strategy_id,
                                     result=result)
                    self.open_trade(strategy_id=strategy_id,
                                    side=position['side'],
                                    trade_size=trade_size)
            else:
                # Draw
                self.close_trade(strategy_id=strategy_id,
                                 result=result)
                self.open_trade(strategy_id=strategy_id,
                                side=position['side'],
                                trade_size=last_trade['trade_size'])

        else:
            # No open position
            dst_price_ema_72 = utils.distance_percent_abs(v1=self.close[0], v2=self.ema_72[0])
            rsi_bullish_from = 40
            rsi_bullish_min = 51
            rsi_bullish_max = 80
            rsi_bearish_from = 60
            rsi_bearish_min = 49
            rsi_bearish_max = 20

            if len(self.datetime) >= 2 and dst_price_ema_72 > 0.0001618:
                # Price is not too close to [ema_72] (0.01618%)

                if self.close[0] > self.ema_72[0]:
                    # Price is above [ema_72]

                    if dst_price_ema_72 < 0.0005:
                        if self.rsi[1] <= rsi_bullish_from and rsi_bullish_min <= self.rsi[0] <= rsi_bullish_max:
                            # Trend Following
                            position = self.open_position(strategy_id=strategy_id,
                                                          side='up',
                                                          trade_size=self.get_optimal_trade_size())

                    else:
                        # Price is too far from [ema_72] (probably loosing strength)
                        if self.rsi[1] >= rsi_bearish_from and rsi_bearish_min >= self.rsi[0] >= rsi_bearish_max:
                            # Against Trend
                            position = self.open_position(strategy_id=strategy_id,
                                                          side='down',
                                                          trade_size=self.get_optimal_trade_size())

                elif self.close[0] < self.ema_72[0]:
                    # Price is bellow [ema_72]

                    if dst_price_ema_72 < 0.0005:
                        if self.rsi[1] >= rsi_bearish_from and rsi_bearish_min >= self.rsi[0] >= rsi_bearish_max:
                            # Trend Following
                            position = self.open_position(strategy_id=strategy_id,
                                                          side='down',
                                                          trade_size=self.get_optimal_trade_size())

                    else:
                        # Price is too far from [ema_72] (probably loosing strength)
                        if self.rsi[1] <= rsi_bullish_from and rsi_bullish_min <= self.rsi[0] <= rsi_bullish_max:
                            # Against Trend
                            position = self.open_position(strategy_id=strategy_id,
                                                          side='up',
                                                          trade_size=self.get_optimal_trade_size())

        return position
