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
pyautogui.PAUSE = 0.5
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

tmsg = utils.tmsg()
logger = Logger()


class SmartTrader:
    broker = None
    region = None

    balance = None
    trade_amount = None
    expiry_time = None

    asset = None
    payout = None
    datetime = []
    open = []
    high = []
    low = []
    close = []
    change = []
    ema_72 = []
    rsi = []

    position_history = []

    # ongoing_positions = {
    #     'ema_rsi': {'asset': 'ABC',
    #                 'strategy_id': 'asb',
    #                 'open_time': 'XXX',
    #                 'side': 'down',
    #                 'result': None,
    #                 'trades': [{'open_time': 'XXX',
    #                             'side': 'up',
    #                             'trade_amount': 1,
    #                             'result': None}]}
    # }
    ongoing_positions = {}

    auto_mode = False
    dry_run_mode = False
    awareness = {
        'balance_equal_to_zero': None,
        'balance_less_than_min_balance': None,
        'payout_low': None,
        'trade_amount_too_high': None
    }

    def __init__(self, broker, region):
        self.broker = broker
        self.region = region

        if not self.is_logged_in:
            # log in
            pass

        for zone in broker['zones'].values():
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

                    f_read = f"read_{element_id}"

                    if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
                        read()

    ''' Validations '''
    def is_logged_in(self):
        return False if self.balance is None else True

    def is_trade_amount_way_too_big(self):
        min_needed_for_martingale = self.trade_amount + \
                                    self.trade_amount * settings.MARTINGALE_MULTIPLIER + \
                                    self.trade_amount * settings.MARTINGALE_MULTIPLIER * 2

        if min_needed_for_martingale > self.balance:
            return False
        return True

    def run_validation(self):
        # Run here the logic to validate screen. It pauses if human is needed
        #   . logged in?
        #   . balance?
        #   . expiry_time?
        #   . trade_amount?
        #   . payout?

        context = 'Validation'

        # Validating readability of elements within the region (user logged in)
        self.__init__(broker=self.broker, region=self.region)

        # Validating [balance]
        if self.balance == 0:
            if not self.awareness['balance_equal_to_zero']:
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc}\t"
                       f"{tmsg.italic}- Your current Balance is [{self.balance} USD]. "
                       f"So I think it makes sense to activate [dry-run] mode, right? {tmsg.endc}")
                tmsg.input(context=context, msg=msg, clear=True)

                self.awareness['balance_equal_to_zero'] = True
                self.dry_run_mode = True

        elif self.balance < settings.MIN_BALANCE:
            if not self.awareness['balance_less_than_min_balance']:
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc}\t"
                       f"{tmsg.italic}- Your current Balance is [{self.balance} USD]. "
                       f"I would recommend at least [{settings.MIN_BALANCE} USD]. {tmsg.endc}")
                tmsg.print(context=context, msg=msg, clear=True)

                msg = f"{tmsg.italic}\n\t- Should I continue anyway? (CTRL-C to abort) {tmsg.endc}"
                tmsg.input(context=context, msg=msg)

                self.awareness['balance_less_than_min_balance'] = True
                self.read_balance()

        # Validating [trade_amount]
        trade_amount_pct = self.trade_amount / self.balance

        while self.dry_run_mode is False and self.is_trade_amount_way_too_big() is False:
            # [trade_amount] couldn't manage Martingale strategy

            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc}\t"
                   f"{utils.tmsg.italic}- I see that Trade Amount is [{self.trade_amount} USD] and "
                   f"your current Balance is [{self.balance} USD]. "
                   f"That means I won't have enough balance available for martingale strategy."
                   f"\n\t- So, here are some options:"
                   f"\n\t\t1. 'Please, change it to an Optimal Trade Size for me' ({settings.OPTIMAL_TRADE_SIZE_PCT}%)"
                   f"\n\t\t2. 'I'll change the [trade_amount] field myself.'"
                   f"\n\t\t3. 'Please, activate [dry-run] mode.'{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            msg = f"{utils.tmsg.italic}\n\t- How do you want to proceed? (1, 2 or 3) (CTRL-C to abort) {utils.tmsg.endc}"
            inp = tmsg.input(context=context, msg=msg)

            if str(inp) == '1':
                optimal_trade_amount = self.balance * settings.OPTIMAL_TRADE_SIZE_PCT
                self.execute_playbook(playbook_id='set_trade_amount', trade_amount=optimal_trade_amount)
            if str(inp) == '2':
                self.read_balance()
                self.read_trade_amount()
            else:
                self.dry_run_mode = True
                msg = f"{utils.tmsg.italic}\t- Ok! [dry-run] mode has been activated.{utils.tmsg.endc}"
                tmsg.print(context=context, msg=msg)
                sleep(1)

        if not self.awareness['trade_amount_too_high'] and trade_amount_pct > settings.MAX_TRADE_SIZE_PCT:
            # [trade_amount] is bigger than recommended

            msg = (f"{utils.tmsg.danger}[WARNING]{utils.tmsg.endc}\t"
                   f"{utils.tmsg.italic}- I see that Trade Amount is [{self.trade_amount} USD] and "
                   f"your current Balance is [{self.balance} USD]. "
                   f"That means [{trade_amount_pct} %]!"
                   f"\n\t- I feel nervous risking that much. But anyway, that's your call:"
                   f"\n\t\t1. 'Please, change it to an Optimal Trade Size' ({settings.OPTIMAL_TRADE_SIZE_PCT}%)"
                   f"\n\t\t2. 'Let's continue with current size.'{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            msg = f"{utils.tmsg.italic}\n\t- How do you want to proceed? (1 or 2) (CTRL-C to abort) {utils.tmsg.endc}"
            inp = tmsg.input(context=context, msg=msg)

            if str(inp) == '1':
                optimal_trade_amount = self.balance * settings.OPTIMAL_TRADE_SIZE_PCT
                self.execute_playbook(playbook_id='set_trade_amount', trade_amount=optimal_trade_amount)
            else:
                self.awareness['trade_amount_too_high'] = True
                msg = f"{utils.tmsg.italic}\t- Ok! Keeping it as it is.{utils.tmsg.endc}"
                tmsg.print(context=context, msg=msg)
                sleep(2)

        # Validating [expiry_time]
        while self.expiry_time is not None and self.expiry_time != '01:00':
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc}\t"
                   f"{utils.tmsg.italic}- Expiry Time is currently set to [{self.expiry_time}], "
                   f"but I'm more expirienced with [01:00]."
                   f"\n\nI'll try to change it myself, so don't worry."
                   f"\nI'll just need your Mouse and Keyboard for a few seconds. :)'{utils.tmsg.endc}")

            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "(CTRL + C to cancel)"
            wait_secs = 10
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_SLEEP_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_SLEEP_TIME)

            # Executing playbook
            self.execute_playbook(playbook_id='set_expiry_time', expiry_time='01:00')

            self.read_expiry_time()
            if self.expiry_time == '01:00':
                print(f"{utils.tmsg.italic}\n\t- Done! {utils.tmsg.endc}")
                sleep(1)

        # Validating [payout]
        while self.payout < 75:
            if not self.awareness['payout_low']:
                msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc}\t"
                       f"{utils.tmsg.italic}- Payout is currently [{self.payout}%]. "
                       f"Maybe it's time to look for another asset? {utils.tmsg.endc}")
                tmsg.print(context=context, msg=msg, clear=True)

                input(f"{utils.tmsg.italic}\n\t- Let me know when I can continue. (CTRL-C to abort) {utils.tmsg.endc}")
                self.awareness['payout_low'] = True

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

                    if 'has_login_info'in zone and zone['has_login_info']:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"Seems like you are not logged in. "
                               f"Or maybe your session window at [{self.broker['name']}] couldn't be found on the "
                               f"expected [monitor] and [region].\n\n"
                               f"Could you check it out, please? :)'{utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        msg = f"{utils.tmsg.italic}\n\t- Let me know when I can try again. (enter){utils.tmsg.endc}"
                        tmsg.input(context=context, msg=msg)

                        # # Waiting PB
                        # msg = "(CTRL + C to cancel)"
                        # wait_secs = 10
                        # items = range(0, int(wait_secs / settings.PROGRESS_BAR_SLEEP_TIME))
                        # for item in utils.progress_bar(items, prefix=msg, reverse=True):
                        #     sleep(settings.PROGRESS_BAR_SLEEP_TIME)
                        #
                        # # Executing playbook
                        # self.execute_playbook(playbook_id='log_in')

                    elif self.auto_mode is False:
                        msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                               f"I couldn't find zone_region for [{zone_id}].\n"
                               f"I see you are logged in just fine but things are not quite in place yet.\n\n"
                               f"This message is just to let you know that I'll fix it by taking control of "
                               f"your Mouse and Keyboard for a few seconds. :)'{utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        # Waiting PB
                        msg = "(CTRL + C to cancel)"
                        wait_secs = 10
                        items = range(0, int(wait_secs / settings.PROGRESS_BAR_SLEEP_TIME))
                        for item in utils.progress_bar(items, prefix=msg, reverse=True):
                            sleep(settings.PROGRESS_BAR_SLEEP_TIME)

                        # Executing playbook
                        self.execute_playbook(playbook_id='tv_chart_setup')

                    else:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"I couldn't find zone_region for [{zone_id}]. "
                               f"I see you are logged in just fine but things are not quite in place yet.\n\n"
                               f"For this one, I'll need some human support. :){utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        msg = f"{utils.tmsg.italic}\n\t- Should I try again? (enter){utils.tmsg.endc}"
                        tmsg.input(msg=msg)

        return zone_region

    def get_ss_path(self, zone_id, context_id=None, element_id=None, template=True):
        if context_id is None:
            context_id = self.broker['id']

        if template:
            return '%s%s__%s.png' % (settings.SS_TEMPLATE_PATH,
                                     context_id,
                                     zone_id)
        else:
            return '%s%s__%s__%s.png' % (settings.SS_PATH,
                                         context_id,
                                         zone_id,
                                         element_id)

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
                    left = width * 0.145
                    top = height * 0.69
                    right = width
                    bottom = height * 0.83
                elif element_id == 'ema_72':
                    left = width * 0.46
                    top = height * 0.86
                    right = width * 0.66
                    bottom = height
            elif zone_id == 'chart_bottom':
                if element_id == 'rsi':
                    left = width * 0.59
                    top = height * 0.03
                    right = width
                    bottom = height * 0.23
            elif zone_id == 'footer':
                if element_id == 'trade_amount':
                    left = width * 0.07
                    top = height * 0.44
                    right = width * 0.40
                    bottom = height * 0.61
                elif element_id == 'expiry_time':
                    left = width * 0.70
                    top = height * 0.33
                    right = width * 0.81
                    bottom = height * 0.45
                elif element_id == 'payout':
                    left = width * 0.05
                    top = height * 0.77
                    right = width * 0.28
                    bottom = height * 0.96

        img = img.crop([left, top, right, bottom])
        return img

    def read_element(self, zone_id, element_id, context_id=None, type='string'):
        # There will be 2 attempts to read the content.

        for attempt in range(1, 2):
            ss_path = None
            if settings.DEBUG_OCR:
                ss_path = self.get_ss_path(zone_id=zone_id,
                                           context_id=context_id,
                                           element_id=element_id,
                                           template=False)

            img = self.screenshot_element(zone_id=zone_id,
                                          element_id=element_id,
                                          save_to=ss_path)

            if type == 'string':
                config = '--psm 7 -c tessedit_char_whitelist="/ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.% "'
            elif type == 'float':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789.'
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

            if not text:
                continue

            return text

    def read_asset(self):
        element_id = 'asset'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])

        value = re.sub("[^A-z/ ]", "", value)

        if self.asset != value:
            # Asset has changed.
            self.reset_chart_data()
            self.awareness['payout_low'] = None

        self.asset = value

        # Renaming PowerShell window name
        os.system(f'title STrader: {value}')

        return self.asset

    def read_balance(self):
        element_id = 'balance'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])
        self.balance = utils.str_to_float(value)
        return self.balance

    def read_trade_amount(self):
        element_id = 'trade_amount'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])
        self.trade_amount = utils.str_to_float(value)
        return self.trade_amount

    def read_chart_data(self):
        # todo: Execute concurrent processes
        o, h, l, c, change = self.read_ohlc()
        ema_72 = self.read_ema_72()
        rsi = self.read_rsi()

        if gmtime().tm_sec >= 58:
            self.datetime.insert(0, strftime("%Y-%m-%d %H:%M:%S", gmtime()))

            self.open.insert(0, o)
            self.high.insert(0, h)
            self.low.insert(0, l)
            self.close.insert(0, c)
            self.change.insert(0, change)

            self.ema_72.insert(0, ema_72)
            self.rsi.insert(0, rsi)

        return [o, h, l, c, ema_72, rsi]

    def reset_chart_data(self):
        self.datetime.clear()
        self.open.clear()
        self.high.clear()
        self.low.clear()
        self.close.clear()
        self.change.clear()

        self.ema_72.clear()
        self.rsi.clear()

    def read_ohlc(self):
        # Returns [change]
        element_id = 'ohlc'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])

        # Extracting only OHLC (ignoring change and change_pct)
        # i_end = utils.find_nth(string=value, substring=' ', n=4)
        # ohlc = value[:i_end]

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

        return [o, h, l, c, change]

    def read_ema_72(self):
        element_id = 'ema_72'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    def read_rsi(self):
        element_id = 'rsi'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    def read_expiry_time(self):
        element_id = 'expiry_time'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])

        self.expiry_time = value
        return self.expiry_time

    def read_payout(self):
        element_id = 'payout'
        value = self.read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                  element_id=element_id,
                                  type=self.broker['elements'][element_id]['type'])
        value = re.sub("[^0-9]", "", value)

        self.payout = int(value)
        return self.payout

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
                element['x'] = zone_region.left + zone_region.width
                element['y'] = zone_region.top
            elif element_id == 'lbl_chart_asset':
                element['x'] = zone_region.left + zone_region.width + 10
                element['y'] = zone_region.top + 15
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
                element['x'] = zone_region.left + 165
                element['y'] = zone_region.top + 228
            elif element_id == 'btn_chart_remove_indicators':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 130
            elif element_id == 'btn_chart_settings':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 235
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
            elif element_id == 'input_rsi_settings_color':
                element['x'] = zone_region.left + 220
                element['y'] = zone_region.top + 130
            elif element_id == 'input_rsi_settings_length':
                element['x'] = zone_region.left + 130
                element['y'] = zone_region.top + 130
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
            elif element_id == 'trade_amount':
                element['x'] = zone_region.left + 150
                element['y'] = zone_region.top + 75
            elif element_id == 'btn_expiry_time':
                element['x'] = zone_region.left + 460
                element['y'] = zone_region.top + 75
            elif element_id == 'btn_up':
                element['x'] = zone_region.left + 100
                element['y'] = zone_region.top + 125
            elif element_id == 'btn_down':
                element['x'] = zone_region.left + 510
                element['y'] = zone_region.top + 125
            elif element_id == 'dp_item_1min':
                element['x'] = zone_center_x
                element['y'] = zone_center_y

        return element

    def click_element(self, element_id, clicks=1, button='left', duration=0.0):
        element = self.get_element(element_id=element_id)
        pyautogui.click(x=element['x'],
                        y=element['y'],
                        clicks=clicks,
                        button=button,
                        duration=duration)

        # After click, wait the same amount of time used for [duration].
        # It gives time for CSS to load and transformations.
        # if [duration] is, we understand it's urgent and there can't be any wait time.
        sleep(duration)

    def move_to_element(self, element_id, duration=0.0):
        element = self.get_element(element_id=element_id)
        pyautogui.moveTo(x=element['x'],
                         y=element['y'],
                         duration=duration)

    def execute_playbook(self, playbook_id, **kwargs):
        self.auto_mode = True
        result = None

        # Moving mouse to monitor (workaround for bug)
        neutral_x = self.region['center_x']
        neutral_y = self.region['height'] * 0.90
        pyautogui.click(x=neutral_x, y=neutral_y)

        f_playbook = f"playbook_{playbook_id}"
        if hasattr(self, f_playbook) and callable(playbook := getattr(self, f_playbook)):
            result = playbook(**kwargs)

        # Click on PS Terminal
        pyautogui.moveTo(x=neutral_x, y=neutral_y)
        self.auto_mode = False
        return result

    def playbook_tv_reset(self):
        # Reseting chart
        self.click_element(element_id='area_chart_background', duration=0.400)
        pyautogui.hotkey('alt', 'r')

        # Removing all indicators
        self.playbook_tv_remove_all_indicators()

    def playbook_tv_remove_all_indicators(self):
        self.click_element(element_id='area_chart_background', button='right', duration=0.400)
        self.click_element(element_id='btn_chart_remove_indicators', duration=0.300)

        # If there is no indicators on the chart, just close dropdown-menu
        pyautogui.press('escape')

    def playbook_tv_chart_setup(self):
        # Chart Type
        self.click_element(element_id='btn_chart_type_candle', duration=0.400)
        sleep(3)

        # Reseting chart
        self.playbook_tv_reset()

        # Defining Chart Settings
        self.playbook_tv_set_chart_settings()

        # Defining EMA 72 up
        self.playbook_tv_add_indicator(hint='Moving Average Exponential')
        self.playbok_tv_configure_indicator_ema(length=72)

        # Defining RSI
        self.playbook_tv_add_indicator(hint='Relative Strength Index')
        self.playbok_tv_configure_indicator_rsi(length=3)

    def playbook_tv_set_chart_settings(self, candle_opacity=5):
        # Opening Chart Settings
        self.click_element(element_id='area_chart_background', button='right', duration=0.400)
        self.click_element(element_id='btn_chart_settings', duration=0.300)

        # Opening Tab 1
        self.click_element(element_id='navitem_chart_settings_tab1', duration=0.300)

        # Configuring [candle_body] opacity
        self.click_element(element_id='input_chart_settings_body_green', duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        self.click_element(element_id='input_chart_settings_body_red', duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        # Configuring [candle_wick] opacity
        self.click_element(element_id='input_chart_settings_wick_green', duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        self.click_element(element_id='input_chart_settings_wick_red', duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')

        # Opening Tab 2
        self.click_element(element_id='navitem_chart_settings_tab2', duration=0.300)

        # Toggling [Bar Change Values]
        self.click_element(element_id='checkbox_chart_settings_bar_change_values', duration=0.300)

        # Scrolling down
        pyautogui.scroll(-500)
        sleep(0.3)

        # Dragging [slider_background_opacity] handler to 100%
        self.move_to_element(element_id='slider_background_opacity', duration=0.300)
        pyautogui.drag(xOffset=75, duration=0.200)

        # Exiting Chart Settings
        pyautogui.press('escape')

    def playbook_tv_add_indicator(self, hint):
        # Opening [btn_chart_indicators] element
        self.click_element(element_id='btn_chart_indicators', duration=0.400)

        # Adding indicator
        pyautogui.typewrite(hint, interval=0.05)
        pyautogui.press('down')
        pyautogui.press('enter')
        pyautogui.press('escape')
        sleep(0.400)

    def playbok_tv_configure_indicator_ema(self, length, color='white', opacity=5):
        # Opening Settings
        self.click_element(element_id='btn_ema_settings', duration=0.400)

        # Configuring settings on Tab 1
        self.click_element(element_id='navitem_ema_settings_tab1', duration=0.300)
        self.click_element(element_id='input_ema_settings_length', clicks=2, duration=0.300)
        pyautogui.typewrite(str(length))

        # Configuring Settings on Tab 2
        self.click_element(element_id='navitem_ema_settings_tab2', duration=0.300)
        self.click_element(element_id='input_ema_settings_color', duration=0.300)
        self.click_element(element_id=f'item_color_{color}', duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')

        # Leaving Settings and Selection
        pyautogui.press('escape')
        pyautogui.press('escape')

    def playbok_tv_configure_indicator_rsi(self, length, color='white', opacity=5):
        # Opening Settings
        self.click_element(element_id='btn_rsi_settings', duration=0.400)

        # Configuring settings on Tab 1
        self.click_element(element_id='navitem_rsi_settings_tab1', duration=0.300)
        self.click_element(element_id='input_rsi_settings_length', clicks=2, duration=0.300)
        pyautogui.typewrite(str(length))

        # Configuring Settings on Tab 2
        self.click_element(element_id='navitem_rsi_settings_tab2', duration=0.300)

        # Setting [color]
        self.click_element(element_id='input_rsi_settings_color', duration=0.300)
        self.click_element(element_id=f'item_color_{color}', clicks=2, duration=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2, duration=0.300)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')

        # Setting [upper_limit]
        self.click_element(element_id='checkbox_rsi_settings_upper_limit', duration=0.300)
        pyautogui.typewrite('80')

        # Setting [lower_limit]
        self.click_element(element_id='checkbox_rsi_settings_lower_limit', duration=0.300)
        pyautogui.typewrite('20')

        # Toggle [hlines_bg]
        self.click_element(element_id='checkbox_rsi_settings_hlines_bg', duration=0.300)

        # Leaving Settings and Selection
        pyautogui.press('escape')
        pyautogui.press('escape')

    def playbook_set_trade_amount(self, trade_amount):
        if self.trade_amount != trade_amount:
            self.click_element(element_id='trade_amount', clicks=2)
            pyautogui.typewrite(str(trade_amount))

    def playbook_set_expiry_time(self, expiry_time='01:00'):
        self.click_element(element_id='btn_expiry_time', duration=0.4)

        if expiry_time == '01:00':
            self.click_element(element_id='dp_item_1min', duration=0.4)

    def playbook_open_trade(self, side, trade_amount=None):
        if trade_amount != self.trade_amount:
            self.playbook_set_trade_amount(trade_amount=trade_amount)

        if side.lower() == 'up':
            self.click_element(element_id='btn_up')
        elif side.lower() == 'down':
            self.click_element(element_id='btn_down')

    ''' Reporting'''

    def df_ongoing_positions(self):
        rows = []
        columns = ['Strategy', 'Side', 'Size', 'Open Time (UTC)']

        for position in self.ongoing_positions.values():
            row = [position['strategy_id'],
                   position['side'],
                   self.trade_amount,
                   position['open_time']]

            i = 1
            for trade in position['trades']:
                if trade['result']:
                    value = trade['result']
                else:
                    value = 'on going'

                columns.append('Trade ' + str(i))
                row.append(value)

                i += 1

            rows.append(row)

        df = pd.DataFrame(data=rows, columns=columns)

        return df

    ''' TA & Trading '''

    def open_position(self, strategy_id, side, trade_amount):
        position = {'result': None}

        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        position['asset'] = self.asset
        position['open_time'] = now
        position['strategy_id'] = strategy_id
        position['side'] = side
        position['trades'] = []

        self.ongoing_positions[strategy_id] = position
        self.open_trade(strategy_id=strategy_id, side=side, trade_amount=trade_amount)

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

        return closed_position

    def open_trade(self, strategy_id, side, trade_amount):
        self.execute_playbook(playbook_id='open_trade', side=side, trade_amount=trade_amount)

        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        trade = {
            'open_time': now,
            'side': self.ongoing_positions[strategy_id]['side'],
            'trade_amount': trade_amount,
            'result': None
        }

        self.ongoing_positions[strategy_id]['trades'].append(trade)
        return trade

    def close_trade(self, strategy_id, result):
        position = self.ongoing_positions[strategy_id]
        position['trades'][-1]['result'] = result

        return position['trades'][-1]

    def start(self):
        msg = "Validating\n"
        tmsg.print(context='Warming Up!',
                   msg=msg,
                   clear=True)

        self.run_validation()
        sec_action = 58.250

        while True:
            context = 'Trading' if self.ongoing_positions else 'Getting Ready!'
            tmsg.print(context=context, clear=True)

            if self.ongoing_positions:
                # Printing [ongoing_positions]

                tb_positions = self.df_ongoing_positions()
                tb_positions = tabulate(tb_positions, headers='keys', showindex=False)
                print(f"{tb_positions}\n\n")

            sec_validation = random.randrange(start=50, stop=55)

            # Waiting PB
            msg = "Observing Price Action"
            if sec_validation > gmtime().tm_sec:
                diff_sec = sec_validation - gmtime().tm_sec
            else:
                diff_sec = sec_validation - gmtime().tm_sec + 60
            items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_SLEEP_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_SLEEP_TIME)

            # Validation PB
            msg = "Quick validation"
            for item in utils.progress_bar([0], prefix=msg):
                self.run_validation()

            if gmtime().tm_sec > sec_validation:
                # Ready for Trading

                # Waiting PB
                msg = "Watching candle closure"
                diff_sec = sec_action - gmtime().tm_sec
                items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_SLEEP_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_SLEEP_TIME)

                self.run_lookup(context=context)

            else:
                # Missed candle data (too late)
                msg = f"{tmsg.warning}We got late and missed last candle's data. \n" \
                      f"Because of that, it's wise to reset chart data.\n\n" \
                      f"But that's no big deal, no actions are needed on your side.{tmsg.endc}"
                tmsg.print(context=context,
                           msg=msg,
                           clear=True)

                self.reset_chart_data()

                wait_time = 5
                sleep(wait_time)

    def run_lookup(self, context):
        position = None
        # Strategies
        msg = "Applying strategies"
        for item in utils.progress_bar([0], prefix=msg):
            self.read_chart_data()

            # Strategies
            position = self.strategy_ema_rsi()

        if position:
            tmsg.print(context=context, clear=True)

            if position['result']:
                art.tprint(text=position['result'], font='block')
                sleep(10)

        return position

    def run_monitoring(self):
        tmsg.print(context='Monitoring', clear=True)

        # reading chart
        tmsg.print(msg='\tReading chart. . . . . .', end='')
        self.read_chart_data()
        msg = f"{utils.tmsg.success}OK{utils.tmsg.endc}"
        tmsg.print(msg=msg)

    def strategy_ema_rsi(self):
        strategy_id = 'ema_rsi'

        if strategy_id in self.ongoing_positions:
            position = self.ongoing_positions[strategy_id]
        else:
            position = None

        if position:
            # Has position open
            result = None
            last_trade = position['trades'][-1]
            amount_trades = position['trades'].__len__()

            if position['side'] == 'up':
                # up
                if self.change[0] > 0:
                    result = 'gain'
                elif self.change[0] < 0:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.change[0] < 0:
                    result = 'gain'
                elif self.change[0] > 0:
                    result = 'loss'
                else:
                    result = 'draw'

            if result == 'gain':
                position = self.close_position(strategy_id=strategy_id,
                                               result=result)
            elif result == 'loss':
                if amount_trades >= settings.MAX_TRADE_AMOUNT_PER_POSITION:
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

                else:
                    # Martingale
                    trade_amount = last_trade['trade_amount'] * settings.MARTINGALE_MULTIPLIER
                    self.close_trade(strategy_id=strategy_id,
                                     result=result)
                    self.open_trade(strategy_id=strategy_id,
                                    side=position['side'],
                                    trade_amount=trade_amount)
            else:
                # Draw
                self.close_trade(strategy_id=strategy_id,
                                 result=result)
                self.open_trade(strategy_id=strategy_id,
                                side=position['side'],
                                trade_amount=last_trade['trade_amount'])

        else:
            # No open position
            if self.datetime.__len__() >= 2:
                if self.close[0] > self.ema_72[0]:
                    # Price above [ema_72]
                    if self.rsi[1] <= 19 and 30 <= self.rsi[0] <= 70:
                        # Trend Following
                        position = self.open_position(strategy_id=strategy_id,
                                                      side='up',
                                                      trade_amount=self.trade_amount)

                elif self.close[0] < self.ema_72[0]:
                    # Price bellow [ema_72]
                    if self.rsi[1] >= 81 and 70 >= self.rsi[0] >= 30:
                        # Trend Following
                        position = self.open_position(strategy_id=strategy_id,
                                                      side='down',
                                                      trade_amount=self.trade_amount)

        return position
