import os
import platform

from cryptography.fernet import Fernet

import json
import random
import re
from time import gmtime, strftime, sleep
from datetime import datetime, timedelta

import asyncio
import subprocess

import art
import pandas as pd
from tabulate import tabulate

from PIL import Image
import mss
import pyautogui
import pytesseract

from engine import settings, utils
from engine.Logger import Logger

pyautogui.FAILSAFE = True
pytesseract.pytesseract.tesseract_cmd = settings.PATH_TESSERACT

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
    highest_balance = 0.00
    initial_trade_size = None
    trade_size = None

    recovery_mode = False
    cumulative_loss = 0.00
    recovery_trade_size = 0.00
    stop_loss_pct = 0.20

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
    #                      'side': 'down',
    #                      'result': None,
    #                      'trades': [{'open_time': 'XXX',
    #                                  'open_price': 0.674804,
    #                                  'trade_size': 1,
    #                                  'result': None}]
    #                      }
    # }

    is_automation_running = False
    awareness = {
        'balance_equal_to_zero': None,
        'balance_less_than_min_balance': None,
        'payout_low': None,
    }

    def __init__(self, agent_id, region, broker, asset, initial_trade_size):
        self.agent_id = agent_id
        self.region = region
        self.broker = broker
        self.asset = asset
        self.initial_trade_size = initial_trade_size

        # Setting [credentials]
        self.validate_credentials()

        # Setting zones
        self.set_zones()

        # Updating [loss_management] data
        self.loss_management_read_from_file()
        self.loss_management_update()

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
        #         print(f"{asset} | "
        #               f"{balance} | "
        #               f"{str(trade_size)} | "
        #               f"{payout} | "
        #               f"{expiry_time} | "
        #               f"{str(chart_data)}")

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

    def get_trading_url(self):
        url = None

        if self.broker['id'] == 'iqcent':
            asset = str(self.asset).replace('/', '-').replace(' ', '_')
            url = self.broker['url']
            url += asset

        return url

    def validate_credentials(self, context='Validation'):
        key_file = 'key'

        if utils.does_file_exist(key_file):
            # Retrieving key
            key = open(file=key_file, mode='r').read()

            # Decoding [credentials]
            fernet = Fernet(key)
            self.broker['credentials']['username'] = fernet.decrypt(self.broker['credentials']['username']).decode()
            self.broker['credentials']['password'] = fernet.decrypt(self.broker['credentials']['password']).decode()

        else:
            # [key_file] doesn't exist
            msg = (f"{utils.tmsg.warning}[ERROR]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- I couldn't find file [{key_file}]. "
                   f"\n\n"
                   f"\t - This file is where you store your generated key using python package [cryptography]. "
                   f"Here are some instructions on how to do it: https://pypi.org/project/cryptography/."
                   f"\n\n"
                   f"\t - Once you have your generated key, use it to encrypt your credentials and update your data "
                   f"for each broker settings.{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            msg = f"{utils.tmsg.italic}\n\t- I'll leave you for know. Take your time. {utils.tmsg.endc}"
            tmsg.input(context=context, msg=msg)
            exit(404)

    def validate_balance(self, context='Validation'):
        if self.balance == 0:
            if not self.awareness['balance_equal_to_zero']:
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc} "
                       f"{tmsg.italic}- Your current Balance is [{self.balance} USD]. "
                       f"\n\n"
                       f"\t  - So I think it makes sense to activate [{settings.MODE_SIMULATION}] mode, right? {tmsg.endc}")

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
                self.read_element(element_id='balance')

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

            self.execute_playbook(playbook_id='set_trade_size', trade_size=optimal_trade_size, is_long_action=True)
            self.read_element(element_id='trade_size')

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
            self.read_element(element_id='expiry_time')

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

    def validate_lookup_duration(self, duration):
        context = 'Validation'
        if duration > settings.MAX_TIME_SPENT_ON_LOOKUP:
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Lookup actions are taking too long. "
                   f"\n\n"
                   f"\t  - A healthy duration would be less than {settings.MAX_TIME_SPENT_ON_LOOKUP} seconds. "
                   f"\n\n"
                   f"\t  - The main reason for such slowness is CPU usage beyond its capacity. If you are running "
                   f"multiple STrader agents in the same host, try to stop one of them.{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Reseting Lookup Trigger (CTRL + C to cancel)"
            wait_secs = 10
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

    def get_optimal_trade_size(self):
        optimal_trade_size = self.initial_trade_size

        if self.recovery_mode:
            optimal_trade_size = self.recovery_trade_size

        return round(optimal_trade_size, 2)

    def is_alerting_session_ended(self):
        zone_id = 'alert_session_ended'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.90)
        if zone_region:
            # Zone [alert_session_ended] has been found
            # Which means session has expired.
            return True

    def is_alerting_not_in_sync(self):
        zone_id = 'alert_not_in_sync'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.90)
        if zone_region:
            # Zone [alert_not_in_sync] has been found
            # Which means session has expired.
            return True

    def is_logged_in(self):
        zone_id = 'header'
        context_id = self.broker['id']
        confidence = self.broker['zones'][zone_id]['locate_confidence']

        ss_template = self.get_ss_path(zone_id=zone_id,
                                       context_id=context_id)
        zone_region = pyautogui.locateOnScreen(ss_template,
                                               region=self.region,
                                               confidence=confidence)
        if zone_region:
            # Zone [header] has been found
            # Which means user is authenticated
            return True

    def is_loss(self, timeout=3):
        zone_id = 'alert_loss'

        # Checking PB
        msg = "Waiting for result confirmation"
        items = range(0, int(timeout / settings.PROGRESS_BAR_INTERVAL_TIME))
        for item in utils.progress_bar(items, prefix=msg, reverse=True):
            zone_region = self.get_zone_region(context_id=self.broker['id'],
                                               zone_id=zone_id,
                                               confidence=0.90)
            if zone_region:
                # Zone [alert_loss] has been found
                # Which means it's a confirmed loss
                return True

    ''' OCR '''

    def get_zone_region(self, context_id, zone_id, confidence=settings.LOCATE_CONFIDENCE):
        context = 'Validation'
        zone_region = None
        ss_template = self.get_ss_path(zone_id=zone_id,
                                       context_id=context_id)
        tries = 0

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
                tries += 1

                if zone_region is None:
                    # Zone couldn't be located on screen
                    zone = self.broker['zones'][zone_id]

                    if 'has_login_info' in zone and zone['has_login_info']:
                        msg = (f"{utils.tmsg.danger}[WARNING]{utils.tmsg.endc} "
                               f"  - Seems like you are not logged in. "
                               f"\n\t  - Or maybe your session window at [{self.broker['name']}] couldn't be found on the "
                               f"expected [monitor] and [region]."
                               f"\n\t  - In any case, let me try to fix it...{utils.tmsg.endc}")
                        tmsg.print(context=context, msg=msg, clear=True)

                        # Waiting PB
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
                        if tries == 1 and zone_id == 'navbar_url':
                            msg = (f"{utils.tmsg.danger}[WARNING]{utils.tmsg.endc} "
                                   f"  - Seems like you don't even have a browser running. "
                                   f"\n\t  - At least I couldn't find it on the "
                                   f"expected [monitor] and [region]."
                                   f"\n\t  - In any case, let me try to fix it...{utils.tmsg.endc}")
                            tmsg.print(context=context, msg=msg, clear=True)

                            # Waiting PB
                            msg = "Looking for Google Chrome icon... I'll find it... (CTRL + C to cancel)"

                            wait_secs = settings.PROGRESS_BAR_WAITING_TIME
                            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                            # Executing playbook
                            self.execute_playbook(playbook_id='open_browser')

                            # Go try to find it again
                            continue

                        if tries >= 5:
                            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                                   f"- I couldn't find zone_region for [{zone_id}]. "
                                   f"\n\t- I see you are logged in just fine but things are not quite in place yet."
                                   f"\n"
                                   f"\n\t- This was my {tries}th attempt, but no success. :/"
                                   f"\n\t- For this one, I'll need some human support. :){utils.tmsg.endc}")
                            tmsg.print(context=context, msg=msg, clear=True)

                            msg = f"{utils.tmsg.italic}\n\t- Should I try again? (enter){utils.tmsg.endc}"
                            tmsg.input(msg=msg)

        return zone_region

    def get_ss_path(self, zone_id, context_id=None, element_id=None, template=True):
        if context_id is None:
            context_id = self.broker['id']

        if template:
            return os.path.join(settings.PATH_SS_TEMPLATE,
                                f'{context_id}__{zone_id}{settings.SS_FILE_EXTENSION}')

        else:
            return os.path.join(settings.PATH_SS,
                                f'{context_id}__{zone_id}__{element_id}{settings.SS_FILE_EXTENSION}')

    def screenshot_element(self, zone_id, element_id, save_to=None):
        zone = self.broker['zones'][zone_id]

        with mss.mss() as ss:
            region_dict = {'left': zone['region'].left,
                           'top': zone['region'].top,
                           'width': zone['region'].width,
                           'height': zone['region'].height}
            img = ss.grab(region_dict)
            img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")

        img = self.crop_screenshot(img=img,
                                   zone_id=zone_id,
                                   element_id=element_id)

        # Converting to grayscale
        img = img.convert('L')

        # Expanding image in 300%
        width, height = img.size
        img = img.resize([int(width * 5), int(height * 5)])

        if save_to:
            img.save(save_to)

        return img

    def crop_screenshot(self, img, zone_id, element_id):
        # Retrieving original measures
        width, height = img.size

        left = top = 0
        right = width
        bottom = height

        if self.broker['id'] == 'iqcent':
            if zone_id == 'header':
                if element_id == 'asset':
                    left = width * 0.08
                    top = height * 0.26
                    right = width * 0.40
                    bottom = height * 0.52
                elif element_id == 'balance':
                    left = width * 0.505
                    top = height * 0.26
                    right = width * 0.80
                    bottom = height * 0.52
            elif zone_id == 'chart_top':
                if element_id == 'ohlc':
                    left = width * 0.15
                    top = height * 0.725
                    right = width
                    bottom = height * 0.84
                elif element_id == 'ema_72':
                    if platform.system().lower() == 'linux':
                        left = width * 0.49
                    else:
                        left = width * 0.465
                    top = height * 0.89
                    right = width * 0.70
                    bottom = height
            elif zone_id == 'chart_bottom':
                if element_id == 'rsi':
                    if platform.system().lower() == 'linux':
                        left = width * 0.61
                    else:
                        left = width * 0.59
                    top = height * 0.04
                    right = width
                    bottom = height * 0.25
            elif zone_id == 'footer':
                if element_id == 'trade_size':
                    left = width * 0.15
                    top = height * 0.46
                    right = width * 0.34
                    bottom = height * 0.60
                if element_id == 'close':
                    left = width * 0.38
                    top = height * 0.76
                    right = width * 0.63
                    bottom = height
                elif element_id == 'expiry_time':
                    left = width * 0.70
                    top = height * 0.33
                    right = width * 0.815
                    bottom = height * 0.47
                elif element_id == 'payout':
                    left = width * 0.10
                    top = height * 0.79
                    right = width * 0.22
                    bottom = height * 0.97

        img = img.crop([left, top, right, bottom])
        return img

    def ocr_read_element(self, zone_id, element_id, context_id=None, type='string'):
        # There will be 2 attempts to read the content.

        for attempt in range(1, 2):
            ss_path = None
            if settings.DEBUG_OCR:
                ss_path = self.get_ss_path(zone_id=zone_id,
                                           context_id=context_id,
                                           element_id=element_id,
                                           template=False)

            start = datetime.now()
            # print(f'[{element_id}] Screenshoting', end=' ... ')
            img = self.screenshot_element(zone_id=zone_id,
                                          element_id=element_id,
                                          save_to=ss_path)
            # print(f'{datetime.now() - start}')

            if type == 'float':
                config = '--psm 7 -c tessedit_char_whitelist=0123456789.'
            elif type == 'string':
                config = '--psm 7 -c tessedit_char_whitelist="/.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "'
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

            # config += ' --oem 1'
            #
            # if os.path.exists(os.path.join(settings.PATH_SS_CONFIG, f'{element_id}.user-patterns')):
            #     config += f' --user-patterns' \
            #               f' {os.path.join(settings.PATH_SS_CONFIG, f"{element_id}.user-patterns")}'
            #
            # if os.path.exists(os.path.join(settings.PATH_SS_CONFIG, f'{element_id}.user-words')):
            #     config += f' --user-words' \
            #               f' {os.path.join(settings.PATH_SS_CONFIG, f"{element_id}.user-words")}'

            # start = datetime.now()
            # print(f'OCR Reading [{element_id}]', end=' ... ')
            text = pytesseract.image_to_string(image=img, config=config)
            # print(f'{datetime.now() - start}')
            text = text.strip()

            if text:
                return text

    def read_element(self, element_id, is_async=False):
        if is_async:
            return self.read_element_async(element_id=element_id)

        # Error handler wrapper of each [read_{element_id}] function
        result = None
        tries = 0
        is_processed = None

        f_read = f"read_{element_id}"
        if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
            while not is_processed:
                tries += 1

                try:
                    if asyncio.iscoroutinefunction(read):
                        # Creating an event loop
                        result = asyncio.run(read())
                    else:
                        result = read()
                    is_processed = True

                except RuntimeError as err:
                    if 'asyncio.run() cannot be called from a running event loop' in str(err):
                        # An event loop is running already
                        # Let's just create a task for it
                        result = asyncio.create_task(read())
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
                        self.execute_playbook(playbook_id='go_to_trading_page')
                        self.run_validation()

                        if asyncio.iscoroutinefunction(read):
                            result = asyncio.run(read())
                        else:
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

    async def read_element_async(self, element_id):
        # Error handler wrapper of each [read_{element_id}] function
        result = None
        tries = 0
        is_processed = None

        f_read = f"read_{element_id}"
        if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
            while not is_processed:
                tries += 1

                try:
                    if asyncio.iscoroutinefunction(read):
                        result = await read()
                    else:
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
                        self.execute_playbook(playbook_id='go_to_trading_page')
                        self.run_validation()

                        if asyncio.iscoroutinefunction(read):
                            result = await read()
                        else:
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

        elif self.asset.replace(' ', '') != value.replace(' ', ''):
            # Asset has changed
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- hmm... Just noticed [asset] changed from [{self.asset}] to [{value}]."
                   f"\n\t  - I'll open [{self.asset}] again, so we can continue on the same asset."
                   f"\n\t  - If you want to change it, please restart me.{utils.tmsg.endc}")
            tmsg.print(msg=msg, clear=True)

            # Waiting PB
            msg = "Loading page (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            self.execute_playbook(playbook_id='go_to_trading_page')

            self.reset_chart_data()
            self.set_awareness(k='payout_low', v=True)

        # Renaming PowerShell window name
        title = f'STrader: {self.asset}'
        utils.set_terminal_title(title=title)

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

        if value > self.highest_balance:
            self.highest_balance = value

        if self.balance:
            if value > self.balance * (1 + self.stop_loss_pct):
                # New value is greater than expected.
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc} "
                       f"{tmsg.italic}- Seems like Your current Balance is [{value} USD], "
                       f"which is way greater than last reading: [{self.balance} USD]. {tmsg.endc}")
                tmsg.print(msg=msg, clear=True)

                msg = f"{tmsg.italic}\n\t- Could you confirm if I read it right? {tmsg.endc}"
                tmsg.input(msg=msg)

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

    async def read_chart_data(self):
        results = await asyncio.gather(
            self.read_ohlc(),
            self.read_ema_72(),
            self.read_rsi(),
            return_exceptions=True
        )

        o, h, l, c, change, change_pct = results[0]
        ema_72 = results[1]
        rsi = results[2]

        now_seconds = utils.now_seconds()
        if now_seconds >= settings.MIN_CHART_DATA_SECONDS or now_seconds <= settings.MAX_CHART_DATA_SECONDS:
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

    async def read_close(self):
        element_id = 'close'

        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = utils.str_to_float(value)

        now_seconds = utils.now_seconds()
        if now_seconds >= settings.MIN_CHART_DATA_SECONDS or now_seconds <= settings.MAX_CHART_DATA_SECONDS:
            self.close[0] = value

        return value

    async def read_ohlc(self):
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
        ohlc = ohlc.split(' ')
        o = utils.str_to_float(ohlc[0][1:])
        h = utils.str_to_float(ohlc[1][1:])
        l = utils.str_to_float(ohlc[2][1:])
        c = utils.str_to_float(ohlc[3][1:])
        change = utils.str_to_float("%.6f" % (c - o))
        change_pct = utils.distance_percent(v1=c, v2=o)

        return [o, h, l, c, change, change_pct]

    async def read_ema_72(self):
        element_id = 'ema_72'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        return utils.str_to_float(value)

    async def read_rsi(self):
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

        if 'locate_confidence' in element:
            confidence = element['locate_confidence']
        else:
            confidence = settings.LOCATE_CONFIDENCE

        # references
        region = self.region

        zone_region = self.get_zone_region(context_id=context_id,
                                           zone_id=element['zone'],
                                           confidence=confidence)

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
                element['x'] = zone_region.left + 220
                element['y'] = zone_region.top + 135
            elif element_id == 'btn_rsi_settings':
                element['x'] = zone_region.left + 175
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
            elif element_id == 'item_color_black':
                element['x'] = zone_region.left + 228
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
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 145
            elif element_id == 'input_chart_settings_body_red':
                element['x'] = zone_region.left + 280
                element['y'] = zone_region.top + 145
            elif element_id == 'input_chart_settings_wick_green':
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 245
            elif element_id == 'input_chart_settings_wick_red':
                element['x'] = zone_region.left + 280
                element['y'] = zone_region.top + 245
            elif element_id == 'input_chart_settings_background':
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 95
            elif element_id == 'input_chart_settings_grid_lines_v':
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 145
            elif element_id == 'input_chart_settings_grid_lines_h':
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 195
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
            elif element_id == 'navitem_chart_settings_tab4':
                element['x'] = zone_region.left + 25
                element['y'] = zone_region.top + 200
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
            elif element_id.startswith('dp_item_'):
                # Matches every [dp_item]
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

    def execute_playbook(self, playbook_id, is_long_action=False, **kwargs):
        self.is_automation_running = True
        result = None

        # Looking for playbook
        f_playbook = f"playbook_{playbook_id}"
        if hasattr(self, f_playbook) and callable(playbook := getattr(self, f_playbook)):
            # Playbook has been found

            if is_long_action is False and playbook_id not in settings.PLAYBOOK_LONG_ACTION:
                # It's not a long action
                result = playbook(**kwargs)

            else:
                # It's a long action
                lock_file = os.path.join(settings.PATH_LOCK,
                                         f'{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}')

                is_done = False
                total_waiting_time = 0
                amount_tries = 0

                while is_done is False:
                    amount_tries += 1

                    try:
                        # Locking it while doing stuff
                        with open(file=lock_file, mode='x') as f:
                            f.write(playbook_id)
                            f.flush()

                            result = playbook(**kwargs)
                            is_done = True

                        # Deleting [lock_file]
                        utils.try_to_delete_file(path=lock_file)

                    except FileExistsError:
                        playbook_id_running = None
                        # Give some time for flush by the other instance.
                        waiting_time = random.randrange(500, 5000) / 1000
                        total_waiting_time += waiting_time
                        sleep(waiting_time)

                        if utils.does_file_exist(path=lock_file):
                            with open(file=lock_file, mode='r') as f:
                                # Retrieving what long_action playbook is running on
                                playbook_id_running = f.read()

                        if playbook_id_running:
                            # Currently running playbook has been identified

                            if total_waiting_time > settings.PLAYBOOK_LONG_ACTION[playbook_id_running] * 2:
                                # It's taking way too long

                                # Trying to remove [lock_file]
                                utils.try_to_delete_file(path=lock_file)

                                result = playbook(**kwargs)
                                is_done = True

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

    def playbook_open_browser(self):
        DETACHED_PROCESS = 0x00000008
        region = self.region
        browser_profile_path = os.path.join(settings.PATH_TEMP_BROWSER_PROFILES, f'profile_{self.agent_id}')

        args = [f'--user-data-dir="{browser_profile_path}"',
                f'--window-position={int(region["x"])},{int(region["y"])}',
                f'--window-size={settings.BROWSER_WIDTH},{settings.BROWSER_HEIGHT}',
                '--log-level=3',
                '--guest',
                '--no-first-run',
                '--disable-notifications']

        if platform.system().lower() == 'windows':
            # Converting args into [str]
            str_args = ''
            for arg in args:
                str_args += f'{arg} '

            # Executing subprocess
            pid = subprocess.Popen(f'"{settings.PATH_BROWSER}" {str_args}',
                                   shell=False,
                                   creationflags=DETACHED_PROCESS).pid
        else:
            # Adding [PATH_BROWSER] to [args] on 1st position
            args.insert(0, settings.PATH_BROWSER)

            # Executing subprocess
            pid = subprocess.Popen(args,
                                   shell=False,
                                   stdin=None,
                                   stdout=None,
                                   stderr=None,
                                   close_fds=True).pid
        sleep(3)

        # Changing focus
        self.mouse_event_on_neutral_area(event='click', area_id='within_app')

    def playbook_log_in(self):
        # Going to [trading_page]
        self.playbook_go_to_trading_page()

        if not self.is_logged_in():
            # User is not logged in

            # Clicking [log_in] button
            self.click_element(element_id='btn_login', wait_when_done=0.500)

            # Filling up credentials
            self.click_element(element_id='input_email')
            pyautogui.typewrite(self.broker['credentials']['username'], interval=0.05)
            pyautogui.press('tab')
            pyautogui.typewrite(self.broker['credentials']['password'], interval=0.05)

            # Confirming login
            self.click_element(element_id='btn_login_confirm', wait_when_done=5)

    def playbook_refresh_page(self):
        pyautogui.click(x=self.region['center_x'], y=self.region['center_y'])
        pyautogui.hotkey('shift', 'f5')

        # Resetting some awareness attributes
        self.set_awareness('payout_low', False)

        # Waiting for page to load
        sleep(5)

    def playbook_go_to_url(self, url=None):
        # Cleaning field
        self.click_element(element_id='input_url')
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')

        # Typing URL
        pyautogui.typewrite(url, interval=0.05)

        # Go
        pyautogui.press('enter')

        # Waiting for page to load
        sleep(5)

    def playbook_go_to_trading_page(self):
        # Going to trading page
        trading_url = self.get_trading_url()
        self.playbook_go_to_url(url=trading_url)

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

    def playbook_tv_set_chart_settings(self, candle_opacity=5, bg_color='white'):
        # Opening Chart Settings
        self.click_element(element_id='area_chart_background', button='right', wait_when_done=0.300)
        self.click_element(element_id='btn_chart_settings', wait_when_done=0.300)

        # Opening Tab 1
        self.click_element(element_id='navitem_chart_settings_tab1', wait_when_done=0.300)

        # [tab1] Configuring [candle_body] opacity
        self.click_element(element_id='input_chart_settings_body_green', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')
        sleep(0.050)

        self.click_element(element_id='input_chart_settings_body_red', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')
        sleep(0.050)

        # [tab1] Configuring [candle_wick] opacity
        self.click_element(element_id='input_chart_settings_wick_green', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')
        sleep(0.050)

        self.click_element(element_id='input_chart_settings_wick_red', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(candle_opacity))
        pyautogui.press('escape')
        sleep(0.050)

        # Opening Tab 2
        self.click_element(element_id='navitem_chart_settings_tab2', wait_when_done=0.300)

        # [tab2] Toggling [Bar Change Values]
        self.click_element(element_id='checkbox_chart_settings_bar_change_values')

        # [tab2] Scrolling down
        pyautogui.scroll(-500)
        sleep(0.300)

        # [tab2] Dragging [slider_background_opacity] handler to 100%
        self.move_to_element(element_id='slider_background_opacity')
        pyautogui.drag(xOffset=100, duration=0.200)

        # Opening Tab 4
        self.click_element(element_id='navitem_chart_settings_tab4', wait_when_done=0.300)

        # [tab4] Setting [color]
        self.click_element(element_id='input_chart_settings_background', wait_when_done=0.300)
        self.click_element(element_id=f'item_color_{bg_color}')
        pyautogui.press('escape')
        sleep(0.050)

        # [tab4] Setting [grid_lines_v] opacity
        self.click_element(element_id='input_chart_settings_grid_lines_v', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite('0')
        pyautogui.press('escape')
        sleep(0.050)

        # [tab4] Setting [grid_lines_h] opacity
        self.click_element(element_id='input_chart_settings_grid_lines_h', wait_when_done=0.300)
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite('0')
        pyautogui.press('escape')
        sleep(0.050)

        # Exiting Chart Settings
        pyautogui.press('escape')

    def playbook_tv_add_indicator(self, hint):
        # Opening [btn_chart_indicators] element
        self.click_element(element_id='btn_chart_indicators', wait_when_done=0.500)

        # Adding indicator
        pyautogui.typewrite(hint, interval=0.05)
        pyautogui.press('down')
        pyautogui.press('enter')
        pyautogui.press('escape')

    def playbok_tv_configure_indicator_ema(self, length, color='black', opacity=25, precision=5):
        # Opening Settings
        self.click_element(element_id='btn_ema_settings', wait_when_done=0.300)

        # [tab1]
        self.click_element(element_id='navitem_ema_settings_tab1', wait_when_done=0.300)

        # [tab1] Setting [length]
        self.click_element(element_id='input_ema_settings_length', clicks=2)
        pyautogui.typewrite(str(length))

        # [tab2]
        self.click_element(element_id='navitem_ema_settings_tab2', wait_when_done=0.300)

        # [tab2] Setting [color]
        self.click_element(element_id='input_ema_settings_color', wait_when_done=0.300)
        self.click_element(element_id=f'item_color_{color}')
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')
        sleep(0.050)

        # [tab2] Setting [precision]
        self.click_element(element_id='input_ema_settings_precision', wait_when_done=0.300)
        self.click_element(element_id=f'dp_item_{precision}')

        # Leaving Settings and Selection
        pyautogui.press(['escape', 'escape'], interval=0.100)

    def playbok_tv_configure_indicator_rsi(self, length, color='black', opacity=25):
        # Opening Settings
        self.click_element(element_id='btn_rsi_settings', wait_when_done=0.300)

        # [tab1]
        self.click_element(element_id='navitem_rsi_settings_tab1', wait_when_done=0.300)

        # [tab1] Setting [length]
        self.click_element(element_id='input_rsi_settings_length', clicks=2)
        pyautogui.typewrite(str(length))

        # [tab2]
        self.click_element(element_id='navitem_rsi_settings_tab2', wait_when_done=0.300)

        # [tab2] Setting [color]
        self.click_element(element_id='input_rsi_settings_color', wait_when_done=0.300)
        self.click_element(element_id=f'item_color_{color}')
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite(str(opacity))
        pyautogui.press('escape')
        sleep(0.050)

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
        self.click_element(element_id='btn_expiry_time', wait_when_done=0.500)

        if expiry_time == '01:00':
            self.click_element(element_id='dp_item_1min')
        else:
            # Option is not supported. Closing dropdown menu
            pyautogui.press('escape')

    async def playbook_open_trade(self, side, trade_size):
        self.playbook_set_trade_size(trade_size=trade_size)

        if side.lower() == 'up':
            self.click_element(element_id='btn_call')
        elif side.lower() == 'down':
            self.click_element(element_id='btn_put')

    ''' Reporting'''

    def df_ongoing_positions(self):
        rows = []
        columns = ['Asset',
                   'Strategy',
                   'Side']

        for position in self.ongoing_positions.values():
            row = [self.asset,
                   position['strategy_id'],
                   position['side']]

            i = 1
            for trade in position['trades']:
                # Adding [trade] columns
                if str(f'T{i}: Open Time') not in columns:
                    columns.append(str(f'T{i}: Open Time'))
                    columns.append(str(f'T{i}: Size'))
                    columns.append(str(f'T{i}: Open Price'))
                    columns.append(str(f'T{i}: Result'))

                # Defining [open_time]
                row.append(trade['open_time'])

                # Defining [size]
                row.append(trade['trade_size'])

                # Defining [open_price]
                row.append(trade['open_price'])

                # Defining [result]
                if trade['result']:
                    value = trade['result']
                else:
                    value = 'on going'

                row.append(value)

                i += 1

            rows.append(row)

        df = pd.DataFrame(data=rows, columns=columns)
        df.fillna('', inplace=True)

        return df

    ''' Loss Management '''

    def get_loss_management_file_path(self):
        return os.path.join(settings.PATH_DATA,
                            f'loss_management_{self.agent_id}.json')

    def loss_management_update(self, result=None, trade_size=0.00):
        # On [initialization], both [result] and [trade_size] can be None/0.00,
        # so [recovery_mode] and [recovery_trade_size] can be calculated based on [settings] and [cumulative_loss]

        if result == 'gain':
            if self.cumulative_loss > 0:
                profit = trade_size * (self.payout / 100)

                # Reducing [cumulative_loss]
                if self.cumulative_loss >= profit:
                    # [cumulative_loss] is greater than [profit]
                    self.cumulative_loss -= profit
                else:
                    # Resetting [recovery_mode]
                    self.recovery_mode = False
                    self.cumulative_loss = 0
        elif result == 'draw':
            pass
        else:
            # System is initializing or it's a new loss

            self.cumulative_loss += trade_size

            # Calculating [payout_offset_compensation] in order to make sure recovery is made with expected amounts
            payout_offset_compensation = 2.00 - (self.payout / 100) + 0.01
            recovery_trade_size = (self.cumulative_loss * payout_offset_compensation /
                                   settings.AMOUNT_TRADES_TO_RECOVER_LOSSES)
            self.recovery_trade_size = round(recovery_trade_size, 2)

            if self.recovery_trade_size < self.initial_trade_size:
                # [recovery_size] would be lesser than [initial_trade_size]
                self.recovery_trade_size = self.initial_trade_size

            if self.recovery_mode:
                # [recovery_mode] is activated
                stop_loss = self.highest_balance * self.stop_loss_pct

                if self.cumulative_loss > stop_loss:
                    # [cumulative_loss] is greater than [stop_loss].
                    # Resetting [recovery_mode]
                    self.recovery_mode = False
                    self.cumulative_loss = 0

            else:
                # [recovery_mode] is not activated yet
                min_position_loss = (self.initial_trade_size * settings.MARTINGALE_MULTIPLIER[0] +
                                     self.initial_trade_size * settings.MARTINGALE_MULTIPLIER[1] +
                                     self.initial_trade_size * settings.MARTINGALE_MULTIPLIER[2])
                if self.cumulative_loss >= min_position_loss:
                    # It's time to activate [recovery_mode]
                    self.recovery_mode = True

    def loss_management_read_from_file(self):
        data = {}

        file_path = self.get_loss_management_file_path()
        if os.path.exists(file_path):
            with open(file=file_path, mode='r') as f:
                data = json.loads(f.read())

            # Updating Loss Management PB
            updatable_fields = ['highest_balance',
                                'recovery_mode',
                                'cumulative_loss']
            msg = "Managing previous losses"
            for k, v in utils.progress_bar(data.items(), prefix=msg):
                if k in updatable_fields:
                    setattr(self, k, v)

        return data

    def loss_management_write_to_file(self):
        data = {'agent_id': self.agent_id,
                'last_asset': self.asset,
                'highest_balance': self.highest_balance,
                'cumulative_loss': self.cumulative_loss,
                'recovery_mode': self.recovery_mode}

        file_path = self.get_loss_management_file_path()
        with open(file=file_path, mode='w') as f:
            f.write(json.dumps(data))

    ''' TA & Trading '''

    async def open_position(self, strategy_id, side, trade_size):
        position = {'result': None,
                    'asset': self.asset,
                    'strategy_id': strategy_id,
                    'side': side,
                    'trades': []}

        self.ongoing_positions[strategy_id] = position
        await self.open_trade(strategy_id=strategy_id, side=side, trade_size=trade_size)

        return position

    async def close_position(self, strategy_id, result):
        # Closing trade and position
        await self.close_trade(strategy_id=strategy_id, result=result)
        self.ongoing_positions[strategy_id]['result'] = result
        closed_position = self.ongoing_positions[strategy_id].copy()

        # [loss_management.json] Writing data in a file for future reference
        self.loss_management_write_to_file()

        # [positions.csv] Appending data to [positions.csv] file
        positions_file = os.path.join(settings.PATH_DATA, 'positions.csv')
        df = self.df_ongoing_positions()
        positions = df.query(f'Strategy == "{strategy_id}"')
        positions.to_csv(positions_file, mode='a', index=False, header=False)

        self.position_history.append(self.ongoing_positions[strategy_id].copy())
        self.ongoing_positions.pop(strategy_id)

        # Checking if we can set [trade_size] to an [optimal_trade_size]
        lock_file = os.path.join(settings.PATH_LOCK,
                                 f'{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}')
        if not os.path.exists(lock_file) or not self.ongoing_positions:
            self.execute_playbook(playbook_id='set_trade_size', trade_size=self.get_optimal_trade_size())

        return closed_position

    async def open_trade(self, strategy_id, side, trade_size):
        # Running concurrently
        await asyncio.gather(
            self.execute_playbook(playbook_id='open_trade', side=side, trade_size=trade_size),
            self.read_element(element_id='close', is_async=True)
        )

        now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        trade = {
            'open_time': now,
            'trade_size': trade_size,
            'open_price': self.close[0],
            'result': None
        }

        self.ongoing_positions[strategy_id]['trades'].append(trade)
        return trade

    async def close_trade(self, strategy_id, result):
        position = self.ongoing_positions[strategy_id]
        trade = position['trades'][-1]
        trade['result'] = result

        # [Loss Management] Updating [cumulative_loss]
        self.loss_management_update(result=result, trade_size=trade['trade_size'])

        # [Loss Management] Write to file on [close_position]...
        # One less action to do in-between trades (when martingale is needed)

        return position['trades'][-1]

    def start(self):
        msg = "Validating\n"
        tmsg.print(context='Warming Up!',
                   msg=msg,
                   clear=True)
        self.run_validation()

        long_action_lock_file = os.path.join(settings.PATH_LOCK,
                                             f'{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}')

        # First run using estimated time (2 seconds)
        lookup_duration = default_lookup_duration = timedelta(seconds=2)
        lookup_trigger = 60 - default_lookup_duration.total_seconds()

        while True:
            context = 'Trading' if self.ongoing_positions else 'Getting Ready'
            tmsg.print(context=context, clear=True)

            # Validating [lookup_duration]
            self.validate_lookup_duration(duration=lookup_duration.total_seconds())

            # Calculating [lookup_trigger]: average with last value
            lookup_trigger = (lookup_trigger + (60 - lookup_duration.total_seconds())) / 2
            print(f'lookup_trigger: {lookup_trigger}')

            if self.ongoing_positions:
                # Printing [ongoing_positions]

                df = self.df_ongoing_positions()
                df = df.filter(items=['Strategy',
                                      'T1: Open Time',
                                      'Side',
                                      'Size',
                                      'T1: Open Price',
                                      'T1: Result',
                                      'T2: Open Price',
                                      'T2: Result',
                                      'T3: Open Price',
                                      'T3: Result'])
                tb_positions = tabulate(df, headers='keys', showindex=False)
                print(f"{tb_positions}\n\n")

            validation_trigger = random.randrange(start=22000, stop=42000) / 1000

            # Waiting PB
            msg = "Watching Price Action"
            if validation_trigger > utils.now_seconds():
                diff_sec = validation_trigger - utils.now_seconds()
            else:
                diff_sec = validation_trigger - utils.now_seconds() + 60

            items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Checking token (only if mouse/keyboard are not being used)
            if utils.does_file_exist(path=long_action_lock_file) is False and len(self.ongoing_positions) == 0:
                # Focusing on App
                self.mouse_event_on_neutral_area(event='click', area_id='within_app')
                sleep(1)
                if self.is_alerting_session_ended():
                    # Alert 401 popping up... Session expired.
                    self.execute_playbook(playbook_id='go_to_trading_page')

            # Validation PB
            msg = "Quick validation"
            for item in utils.progress_bar([0], prefix=msg):
                self.run_validation()

            if validation_trigger <= utils.now_seconds() < lookup_trigger:
                # Ready for Trading

                # Waiting PB
                msg = "Watching candle closure"
                diff_sec = lookup_trigger - utils.now_seconds()

                items = range(0, int(diff_sec / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                # Running Lookup
                start = datetime.now()
                asyncio.run(self.run_lookup(context=context))
                lookup_duration = datetime.now() - start

                if len(self.ongoing_positions) > 0:
                    # A [trade] has been probably open

                    # Checking if session is still in sync
                    sleep(random.randrange(750, 1750) / 1000)
                    if self.is_alerting_not_in_sync():
                        # Alert [not_in_sync] popping up... Refreshing page

                        # Cleaning up
                        self.reset_chart_data()
                        self.ongoing_positions.clear()

                        # Refreshing page
                        self.execute_playbook(playbook_id='go_to_trading_page')

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

                # Reseting [lookup_duration]
                lookup_trigger = 60 - default_lookup_duration.total_seconds()

                waiting_time = 5
                sleep(waiting_time)

    async def run_lookup(self, context):
        # Strategies
        msg = "Applying strategies"
        strategies = settings.TRADING_STRATEGIES.copy()

        # Reading Chart data
        start = datetime.now()
        await self.read_element(element_id='chart_data', is_async=True)
        print(f'[chart_data] reading took: {datetime.now() - start}')

        # Preparing tasks
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for strategy in utils.progress_bar(strategies, prefix=msg):
                f_strategy = f"strategy_{strategy}"

                if hasattr(self, f_strategy) and callable(strategy := getattr(self, f_strategy)):
                    tasks.append(tg.create_task(strategy()))
                else:
                    # Strategy not found
                    msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                           f"- That's embarrassing. :/ "
                           f"\n\t- I couldn't find a function for strategy [{strategy}].! :/"
                           f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
                    tmsg.input(msg=msg, clear=True)
                    exit(500)

        if len(self.ongoing_positions) == 0:
            # There are no open positions

            for task in tasks:
                position = task.result()

                if position and position['result']:
                    # Position has been closed
                    tmsg.print(context=context, clear=True)
                    art.tprint(text=position['result'], font='block')
                    await asyncio.sleep(2)

    async def strategy_ema_rsi_8020(self):
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
                if self.close[0] > last_trade['open_price']:
                    result = 'gain'
                elif self.close[0] < last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.close[0] < last_trade['open_price']:
                    result = 'gain'
                elif self.close[0] > last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            if result == 'gain':
                position = await self.close_position(strategy_id=strategy_id,
                                                     result=result)
            elif result == 'loss':
                if amount_trades >= settings.MAX_TRADES_PER_POSITION:
                    # No more tries
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)

                elif position['side'] == 'up' and self.rsi[0] < 20:
                    # Abort it
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)
                elif position['side'] == 'down' and self.rsi[0] > 80:
                    # Abort it
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)

                if not position['result']:
                    # Martingale
                    await self.close_trade(strategy_id=strategy_id,
                                           result=result)

                    if self.recovery_mode:
                        trade_size = self.get_optimal_trade_size()
                    else:
                        trade_size = last_trade['trade_size'] * settings.MARTINGALE_MULTIPLIER[amount_trades]

                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=trade_size)
            else:
                # Draw
                await self.close_trade(strategy_id=strategy_id,
                                       result=result)
                await self.open_trade(strategy_id=strategy_id,
                                      side=position['side'],
                                      trade_size=last_trade['trade_size'])

        else:
            # No open position
            if len(self.datetime) >= 2:
                dst_price_ema_72 = utils.distance_percent_abs(v1=self.close[0], v2=self.ema_72[0])

                if self.close[0] > self.ema_72[0] or dst_price_ema_72 < -0.0005:
                    # Price is above [ema_72] or far bellow [ema_72]

                    if self.rsi[1] <= 20 and 30 <= self.rsi[0] <= 70:
                        position = await self.open_position(strategy_id=strategy_id,
                                                            side='up',
                                                            trade_size=self.get_optimal_trade_size())

                elif self.close[0] < self.ema_72[0] or dst_price_ema_72 > 0.0005:
                    # Price is bellow [ema_72] or far above [ema_72]
                    if self.rsi[1] >= 80 and 70 >= self.rsi[0] >= 30:
                        # Trend Following
                        position = await self.open_position(strategy_id=strategy_id,
                                                            side='down',
                                                            trade_size=self.get_optimal_trade_size())

        return position

    async def strategy_ema_rsi_50(self):
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
                if self.close[0] > last_trade['open_price']:
                    result = 'gain'
                elif self.close[0] < last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.close[0] < last_trade['open_price']:
                    result = 'gain'
                elif self.close[0] > last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            # Checking [result]
            if result == 'gain':
                position = await self.close_position(strategy_id=strategy_id,
                                                     result=result)
            elif result == 'loss':
                if amount_trades >= settings.MAX_TRADES_PER_POSITION:
                    # No more tries
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)

                elif position['side'] == 'up':
                    if self.rsi[0] < 38:
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)
                    elif self.close[1] > self.ema_72[1] and self.close[0] < self.ema_72[0]:
                        # [close] crossed [ema_72] up
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)
                elif position['side'] == 'down':
                    if self.rsi[0] > 62:
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)
                    elif self.close[1] < self.ema_72[1] and self.close[0] > self.ema_72[0]:
                        # [close] crossed [ema_72] down
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)

                if not position['result']:
                    # Martingale
                    await self.close_trade(strategy_id=strategy_id,
                                           result=result)

                    if self.recovery_mode:
                        trade_size = self.get_optimal_trade_size()
                    else:
                        trade_size = last_trade['trade_size'] * settings.MARTINGALE_MULTIPLIER[amount_trades]

                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=trade_size)
            else:
                # Draw
                await self.close_trade(strategy_id=strategy_id,
                                       result=result)
                await self.open_trade(strategy_id=strategy_id,
                                      side=position['side'],
                                      trade_size=last_trade['trade_size'])

        else:
            # No open position
            if len(self.datetime) >= 2:
                dst_price_ema_72 = utils.distance_percent_abs(v1=self.close[0], v2=self.ema_72[0])
                rsi_bullish_from = 39
                rsi_bullish_min = 51
                rsi_bullish_max = 80
                rsi_bearish_from = 61
                rsi_bearish_min = 49
                rsi_bearish_max = 20

                if dst_price_ema_72 > 0.0001618:
                    # Price is not too close to [ema_72] (0.01618%)

                    if self.close[0] > self.ema_72[0]:
                        # Price is above [ema_72]

                        if dst_price_ema_72 < 0.0005:
                            # Price is not too far from [ema_72] (0.05%)
                            if self.rsi[1] <= rsi_bullish_from and rsi_bullish_min <= self.rsi[0] <= rsi_bullish_max:
                                # Trend Following
                                position = await self.open_position(strategy_id=strategy_id,
                                                                    side='up',
                                                                    trade_size=self.get_optimal_trade_size())

                        elif dst_price_ema_72 > 0.0007:
                            # Price is too far from [ema_72] (probably losing strength)
                            if self.rsi[1] >= rsi_bearish_from and rsi_bearish_min >= self.rsi[0] >= rsi_bearish_max:
                                # Against Trend
                                position = await self.open_position(strategy_id=strategy_id,
                                                                    side='down',
                                                                    trade_size=self.get_optimal_trade_size())

                    elif self.close[0] < self.ema_72[0]:
                        # Price is bellow [ema_72]

                        if dst_price_ema_72 < 0.0005:
                            if self.rsi[1] >= rsi_bearish_from and rsi_bearish_min >= self.rsi[0] >= rsi_bearish_max:
                                # Trend Following
                                position = await self.open_position(strategy_id=strategy_id,
                                                                    side='down',
                                                                    trade_size=self.get_optimal_trade_size())

                        elif dst_price_ema_72 > 0.0007:
                            # Price is too far from [ema_72] (probably losing strength)
                            if self.rsi[1] <= rsi_bullish_from and rsi_bullish_min <= self.rsi[0] <= rsi_bullish_max:
                                # Against Trend
                                position = await self.open_position(strategy_id=strategy_id,
                                                                    side='up',
                                                                    trade_size=self.get_optimal_trade_size())

        return position
