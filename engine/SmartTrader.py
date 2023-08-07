import os
import platform

from cryptography.fernet import Fernet

import requests
import json
import random
import re
from time import sleep
from datetime import datetime, timedelta

import asyncio
import subprocess

import art
import pandas as pd
from tabulate import tabulate

from PIL import Image, ImageOps
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

    clock = None
    expiry_time = None
    payout = None

    asset = None
    datetime = []
    open = []
    high = []
    low = []
    close = []
    change = []
    change_pct = []

    price = []

    ema_50 = []
    ema_21 = []
    ema_9 = []
    rsi = []

    position_history = []

    ongoing_positions = {}
    # ongoing_positions = {
    #     'ema_rsi_8020': {'asset': 'ABC',
    #                      'strategy_id': 'ema_rsi_8020',
    #                      'side': 'down',
    #                      'stop_loss: None,
    #                      'result': None,
    #                      'trades': [{'open_time': datetime.utcnow(),
    #                                  'open_price': 0.674804,
    #                                  'trade_size': 1,
    #                                  'result': None}]
    #                      }
    # }

    is_automation_running = None
    is_super_strike_active = None
    ignore_trading_window = None
    awareness = {
        'balance_equal_to_zero': None,
        'balance_less_than_min_balance': None,
    }

    def __init__(self, agent_id, region, broker, asset, initial_trade_size, ignore_trading_window):
        self.agent_id = agent_id
        self.region = region
        self.broker = broker
        self.asset = asset
        self.initial_trade_size = initial_trade_size
        self.ignore_trading_window = ignore_trading_window

        # Setting [credentials]
        self.validate_credentials()

        # Setting zones
        self.set_zones()

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
            raise RuntimeError(f'Awareness key [{k}] not found.')

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
        if settings.DEBUG_OCR:
            while True:
                # self.execute_playbook('refresh_page')

                asset = self.read_element(element_id='asset')
                balance = self.read_element(element_id='balance')
                clock = self.read_element(element_id='clock')
                payout = self.read_element(element_id='payout')
                chart_data = asyncio.run(self.read_chart_data(element_ids=None))
                ohlc = self.read_element(element_id='ohlc')
                price = self.read_element(element_id='price')
                trade_size = self.read_element(element_id='trade_size')
                expiry_time = self.read_element(element_id='expiry_time')

                print(f"asset: {asset}\t | balance: {balance}\t | clock: {clock}"
                      f"\ntrade_size: {str(trade_size)}\t | payout: {payout}\t | expiry_time: {expiry_time}"
                      f"\nchart_data: {str(chart_data)}"
                      f"\nohlc: {str(ohlc)}"
                      f"\nprice: {str(price)}")
                print()

    def run_validation(self):
        # Run here the logic to validate screen. It pauses if human is needed
        #   . logged in?
        #   . balance?
        #   . expiry_time?
        #   . trade_size?
        #   . payout?

        context = 'Validation'

        # Validating trading session
        self.validate_trading_session()

        # Validating readability of elements within the region (user logged in)
        self.set_zones()

        # Validating [clock]
        self.validate_clock(context=context)

        # Validating [balance]
        self.validate_balance(context=context)

        # Validating [expiry_time]
        self.validate_expiry_time(context=context)

        # Validating [payout]
        self.validate_payout(context=context)

        # Updating [loss_management] data
        self.loss_management_sync()

        # Validating [trade_size]
        self.validate_trade_size(context=context)

        # Validating [super_strike]
        self.validate_super_strike(context=context)

    def get_asset_for_url_path(self):
        asset = None
        if self.broker['id'] == 'iqcent':
            asset = str(self.asset).replace('/', '-').replace(' ', '_')

        return asset

    def get_trading_url(self):
        url = None
        asset = self.get_asset_for_url_path()

        if self.broker['id'] == 'iqcent':
            url = self.broker['url']
            url += asset

        return url

    def validate_trading_session(self, context='Validation'):
        if not self.ignore_trading_window:
            now = datetime.utcnow()

            trading_start = 6
            trading_end = 19

            while now.hour < trading_start or now.hour > trading_end:
                msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                       f"{utils.tmsg.italic}- We are currently out of the trading time range, "
                       f"which should be between {trading_start} and {trading_end}. {utils.tmsg.endc}")
                tmsg.print(context=context, msg=msg, clear=True)

                # Waiting PB
                msg = "Waiting for it (CTRL + C to cancel)"
                wait_secs = 300
                items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                now = datetime.utcnow()

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
            raise RuntimeError(f'File holding credencial keys [{key_file}] not found.')

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

                # Waiting PB
                msg = "Should I continue anyway? (CTRL-C to abort)"
                wait_secs = 10
                items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                self.set_awareness(k='balance_less_than_min_balance', v=True)
                self.read_element(element_id='balance')

    def validate_clock(self, context='Validation'):
        # First reading
        now = datetime.utcnow()
        clock = self.read_element(element_id='clock')
        app_now = datetime.fromisoformat(f'{now.date().isoformat()} {clock}')
        delta = now - app_now
        tries = 0

        while abs(delta.total_seconds()) > 1.5:
            # Out of sync confirmed

            wait_secs = 3
            tries += 1

            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Seems like broker's clock is not synchronized with computer's clock."
                   f"\n"
                   f"\t  - Right now, the difference between computer's clock and "
                   f"broker's clock is {abs(delta.total_seconds())} seconds."
                   f"\n\n"
                   f"\t  - Let me try to fix it...{utils.tmsg.endc}")

            tmsg.print(context=context, msg=msg, clear=True)

            if tries == 1:
                # Waiting PB
                msg = "Synchronizing clock with a NTP server... (CTRL + C to cancel)"
                items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                # Executing playbook
                self.execute_playbook(playbook_id='sync_clock_with_ntp_server')

            elif tries == 2:
                # Waiting PB
                msg = "Refreshing page (CTRL + C to cancel)"
                items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                # Executing playbook
                self.execute_playbook(playbook_id='go_to_trading_page')
                self.run_validation()
            else:
                msg = f"{utils.tmsg.italic}\n\t  - I couldn't fix it. :/ {utils.tmsg.endc}"
                tmsg.print(context=context, msg=msg)
                raise RuntimeError(f'Issue could not be fixed.')

            # Retrieving [now] and reading [clock] for next loop
            now = datetime.utcnow()
            clock = self.read_element(element_id='clock')
            app_now = datetime.fromisoformat(f'{now.date().isoformat()} {clock}')
            delta = now - app_now

    def validate_trade_size(self, context='Validation'):
        optimal_trade_size = self.get_optimal_trade_size()

        if len(self.ongoing_positions) == 0 and self.trade_size != optimal_trade_size:
            # [trade_size] is different from [initial_trade_size]

            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Just noticed that Trade Size is [{self.trade_size} USD], "
                   f"and the Optimal Trade Size right now would be [{optimal_trade_size} USD]. "
                   f"\n"
                   f"\t  - I'll take care of that...{utils.tmsg.endc}")
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
        expected_expiry_time = '01:00'

        while not self.is_expiry_time_fixed():
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Expiry Time is not set to [fixed] as I would expect."
                   f"\n"
                   f"\n\t  - I'll set it up for us.{utils.tmsg.endc}")

            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Toggling Expiry Time to Fixed (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Executing playbook
            self.execute_playbook(playbook_id='toggle_expiry_time')
            self.read_element(element_id='expiry_time')

            print(f"{utils.tmsg.italic}\n\t  - Done! {utils.tmsg.endc}")
            sleep(1)

        while self.expiry_time != expected_expiry_time:
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Expiry Time is currently set to [{self.expiry_time}], "
                   f"but I'm more experienced with [{expected_expiry_time}]."
                   f"\n"
                   f"\n\t  - Let me try to update it.{utils.tmsg.endc}")

            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Setting Expiry Time (CTRL + C to cancel)"
            wait_secs = 1
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Executing playbook
            self.execute_playbook(playbook_id='set_expiry_time', expiry_time=expected_expiry_time)
            self.read_element(element_id='expiry_time')

            if self.expiry_time == expected_expiry_time:
                print(f"{utils.tmsg.italic}\n\t  - Done! {utils.tmsg.endc}")
                sleep(1)

    def validate_payout(self, context='Validation'):
        while self.payout < settings.MIN_PAYOUT:
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Payout is currently [{self.payout}%]. "
                   f"Maybe it's time to look for another asset? {utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            # Waiting PB
            msg = "Waiting for payout get higher again (CTRL + C to cancel)"
            wait_secs = 300
            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            self.playbook_go_to_trading_page()
            self.read_element(element_id='payout')

    def validate_super_strike(self, context='Validation'):
        if self.asset.endswith('OTC'):
            if not self.is_super_strike_activated():
                # [super_strike] hasn't been activated yet

                if self.is_super_strike_available():
                    # It's available to be activated
                    self.execute_playbook(playbook_id='activate_super_strike')

    def is_reading_taking_too_long(self, element_id, duration):
        context = 'Validation'

        if element_id == 'chart_data' and duration > settings.CHART_DATA_READING_LIMIT_SECONDS:
            msg = (f"{utils.tmsg.warning}[WARNING]{utils.tmsg.endc} "
                   f"{utils.tmsg.italic}- Lookup actions are taking too long: {duration} seconds."
                   f"\n\n"
                   f"\t  - A healthy duration would be less than {settings.CHART_DATA_READING_LIMIT_SECONDS} seconds. "
                   f"\n\n"
                   f"\t  - The main reason for such slowness is CPU usage beyond its capacity. If you are running "
                   f"multiple STrader agents in the same host, try to stop one of them.{utils.tmsg.endc}")
            tmsg.print(context=context, msg=msg, clear=True)

            return True

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

    def is_expiry_time_fixed(self):
        zone_id = 'expiry_time_fixed'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.98)
        if zone_region:
            # Zone [alert_not_in_sync] has been found
            # Which means session has expired.
            return True

    def is_super_strike_available(self):
        zone_id = 'super_strike_available'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.98)
        if zone_region:
            # Zone [super_strike_available] has been found
            # Which means it's available but not activated yet.
            return True

    def is_super_strike_activated(self):
        zone_id = 'super_strike_activated'
        zone_region = self.get_zone_region(context_id=self.broker['id'],
                                           zone_id=zone_id,
                                           confidence=0.98)
        if zone_region:
            # Zone [super_strike_activated] has been found
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
            while zone_region is None:
                zone_region = pyautogui.locateOnScreen(ss_template,
                                                       region=self.region,
                                                       confidence=confidence)
                tries += 1

                if tries >= 3:
                    return zone_region

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

                        msg = f"\t  - Done !"
                        tmsg.print(context=context, msg=msg)
                        sleep(1)

                    elif not self.is_automation_running:
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
                        if zone_id == 'chart_top' and len(self.datetime) == 0:
                            # Browser just got launched
                            self.execute_playbook(playbook_id=f"{self.broker['id']}_chart_setup")
                        else:
                            self.execute_playbook(playbook_id='go_to_trading_page')

                        msg = f"\t  - Done !"
                        tmsg.print(context=context, msg=msg)
                        sleep(1)

                    else:
                        if tries == 1:
                            # Use this block to specify workarounds when
                            # a specific zone can't be found on the first attempt
                            if zone_id == 'navbar_url':
                                msg = (f"{utils.tmsg.danger}[WARNING]{utils.tmsg.endc} "
                                       f"- Seems like you don't even have a browser running. "
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

                        if tries >= settings.MAX_TRIES_LOCATING_ELEMENT:
                            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                                   f"- I couldn't find zone_region for [{zone_id}]. "
                                   f"\n\t- I see you are logged in just fine but things are not quite in place yet."
                                   f"\n"
                                   f"\n\t- This was my {tries}th attempt, but no success. :/"
                                   f"\n\t- For this one, I'll need some human support. :){utils.tmsg.endc}")
                            tmsg.print(context=context, msg=msg, clear=True)

                            msg = f"{utils.tmsg.italic}- Should I try again? (enter){utils.tmsg.endc}"
                            wait_secs = 60
                            items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                            # Execute playbook
                            self.reset_chart_data()
                            self.execute_playbook(playbook_id='go_to_trading_page')

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

        # Inverting colors
        img = ImageOps.invert(img)

        # Expanding image in 300%
        width, height = img.size
        img = img.resize([int(width * 4), int(height * 4)])

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
                    left = width * 0.07
                    top = height * 0.26
                    right = width * 0.40
                    bottom = height * 0.525
                elif element_id == 'balance':
                    left = width * 0.505
                    top = height * 0.26
                    right = width * 0.80
                    bottom = height * 0.525
            elif zone_id == 'chart_top':
                if element_id == 'ohlc':
                    left = width * 0.11
                    top = height * 0.38
                    right = width
                    bottom = height * 0.47
                elif element_id == 'ema_50':
                    if platform.system().lower() == 'linux':
                        left = width * 0.51
                    else:
                        left = width * 0.45
                    top = height * 0.46
                    right = width * 0.75
                    bottom = height * 0.55
                elif element_id == 'ema_21':
                    if platform.system().lower() == 'linux':
                        left = width * 0.51
                    else:
                        left = width * 0.45
                    top = height * 0.55
                    right = width * 0.75
                    bottom = height * 0.64
                elif element_id == 'ema_9':
                    if platform.system().lower() == 'linux':
                        left = width * 0.49
                    else:
                        left = width * 0.43
                    top = height * 0.64
                    right = width * 0.75
                    bottom = height * 0.73
                elif element_id == 'clock':
                    left = width * 0.26
                    top = height * 0.095
                    right = width * 0.425
                    bottom = height * 0.195
            elif zone_id == 'chart_bottom':
                if element_id == 'rsi':
                    left = width * 0.67
                    top = 0
                    right = width * 0.925
                    bottom = height * 0.235
            elif zone_id == 'footer':
                if element_id == 'trade_size':
                    if platform.system().lower() == 'linux':
                        top = height * 0.43
                        bottom = height * 0.59
                    else:
                        top = height * 0.45
                        bottom = height * 0.61
                    left = width * 0.15
                    right = width * 0.34
                if element_id == 'price':
                    if platform.system().lower() == 'linux':
                        top = height * 0.75
                    else:
                        top = height * 0.77
                    left = width * 0.38
                    right = width * 0.63
                    bottom = height * 0.985
                elif element_id == 'expiry_time':
                    left = width * 0.71
                    top = height * 0.32
                    right = width * 0.82
                    bottom = height * 0.465
                elif element_id == 'payout':
                    left = width * 0.10
                    top = height * 0.78
                    right = width * 0.22
                    bottom = height * 0.96

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
                config = '--psm 7 -c tessedit_char_whitelist="0123456789,. ABCDEFGHIJKLMNOPQRSTUVWXYZ"'
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

    def read_element(self, element_id, is_async=False, **kwargs):
        if is_async:
            return self.read_element_async(element_id=element_id, **kwargs)

        # Error handler wrapper of each [read_{element_id}] function
        result = None
        tries = 0
        is_processed = None

        f_read = f"read_{element_id}"
        if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
            while not is_processed:
                tries += 1

                if tries > 1:
                    print(f'{element_id}: {datetime.now().time()} Running attempt {tries}...')

                try:
                    if asyncio.iscoroutinefunction(read):
                        # Creating an event loop
                        result = asyncio.run(read(**kwargs))
                    else:
                        result = read(**kwargs)
                    is_processed = True

                except RuntimeError as err:
                    if 'asyncio.run() cannot be called from a running event loop' in str(err):
                        # An event loop is running already
                        # Let's just create a task for it
                        result = asyncio.create_task(read(**kwargs))
                        is_processed = True

                except Exception as err:
                    if tries > settings.MAX_TRIES_READING_ELEMENT:
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
                            result = asyncio.run(read(**kwargs))
                        else:
                            result = read(**kwargs)
                        is_processed = True

                if is_processed and result is None:
                    # It's been processed, but content is None
                    # Try again...
                    is_processed = False

                    if tries >= settings.MAX_TRIES_READING_ELEMENT:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"- I'm trying to read [{element_id}]. "
                               f"\n\t- I could locate its region on screen, but I keep reading [{result}]."
                               f"\n"
                               f"\n\t- This was my {tries}th attempt, but no success. :/"
                               f"\n\t- For this one, I'll need some human support. :){utils.tmsg.endc}")
                        tmsg.print(msg=msg, clear=True)

                        msg = f"{utils.tmsg.italic}\n\t- Should I try again? (enter){utils.tmsg.endc}"
                        tmsg.input(msg=msg)

        else:
            # Function not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n- I couldn't find function [{f_read}]!"
                   f"\n- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            raise RuntimeError(f'Function [{f_read}] not found.')

        return result

    async def read_element_async(self, element_id, **kwargs):
        # Error handler wrapper of each [read_{element_id}] function
        result = None
        tries = 0
        is_processed = None

        f_read = f"read_{element_id}"
        if hasattr(self, f_read) and callable(read := getattr(self, f_read)):
            while not is_processed:
                tries += 1

                if tries > 1:
                    print(f'{element_id}: {datetime.now().time()} Running attempt {tries}...')

                try:
                    if asyncio.iscoroutinefunction(read):
                        result = await read(**kwargs)
                    else:
                        result = read(**kwargs)
                    is_processed = True

                except RuntimeError as err:
                    if 'asyncio.run() cannot be called from a running event loop' in str(err):
                        # An event loop is running already
                        # Let's just create a task for it
                        result = asyncio.create_task(read(**kwargs))
                        is_processed = True

                except Exception as err:
                    if tries > settings.MAX_TRIES_READING_ELEMENT:
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
                            result = await read(**kwargs)
                        else:
                            result = read(**kwargs)
                        is_processed = True

                if is_processed and result is None:
                    # It's been processed, but content is None
                    # Try again...
                    is_processed = False

                    if tries >= settings.MAX_TRIES_READING_ELEMENT:
                        msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                               f"- I'm trying to read [{element_id}]. "
                               f"\n\t- I could locate its region on screen, but I keep reading [{result}]."
                               f"\n"
                               f"\n\t- This was my {tries}th attempt, but no success. :/"
                               f"\n\t- For this one, I'll need some human support. :){utils.tmsg.endc}")
                        tmsg.print(msg=msg, clear=True)

                        msg = f"{utils.tmsg.italic}\n\t- Should I try again? (enter){utils.tmsg.endc}"
                        tmsg.input(msg=msg)

        else:
            # Function not found
            msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                   f"- That's embarrassing. :/ "
                   f"\n- I couldn't find function [{f_read}]!"
                   f"\n- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
            raise RuntimeError(f'Function [{f_read}] not found.')

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
            if value > self.balance * 2:
                # New value is greater than expected.
                msg = (f"{tmsg.warning}[WARNING]{tmsg.endc} "
                       f"{tmsg.italic}- Seems like Your current Balance is [{value} USD], "
                       f"which is way greater than last reading: [{self.balance} USD]. {tmsg.endc}")
                tmsg.print(msg=msg, clear=True)

                msg = f"{tmsg.italic}\n\t- Could you confirm if I read it right? {tmsg.endc}"
                tmsg.input(msg=msg)

        self.balance = value
        return self.balance

    def read_clock(self):
        element_id = 'clock'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])

        # Validating [clock] format
        datetime.fromisoformat(f'{datetime.now().date().isoformat()} {value}')

        self.clock = value
        return self.clock

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

    async def read_chart_data(self, element_ids=None):
        # Reads [chart_data] plus add an entry in [self.datetime]
        tasks = []
        result = []

        if element_ids is None:
            # Default chart elements
            element_ids = ['ema_50', 'ema_21', 'ema_9', 'rsi']

        action = None
        now = datetime.utcnow()
        if now.second >= settings.CHART_DATA_MIN_SECONDS or now.second <= settings.CHART_DATA_MAX_SECONDS:
            action = 'insert'

            # Calculating candle's [datetime]
            if now.second > settings.CHART_DATA_MIN_SECONDS:
                candle_datetime = now - timedelta(seconds=now.second)
            else:
                candle_datetime = now - timedelta(minutes=1, seconds=now.second)

            self.datetime.insert(0, candle_datetime.strftime("%Y-%m-%d %H:%M:%S"))

        async with asyncio.TaskGroup() as tg:
            for element_id in element_ids:
                tasks.append(tg.create_task(self.read_element(element_id=element_id,
                                                              is_async=True,
                                                              action=action)))
        for task in tasks:
            result.append(task.result())

        return result

    def reset_chart_data(self):
        self.datetime.clear()
        self.open.clear()
        self.high.clear()
        self.low.clear()
        self.close.clear()
        self.change.clear()
        self.change_pct.clear()

        self.ema_50.clear()
        self.rsi.clear()

    async def read_price(self, action=None):
        element_id = 'price'

        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = utils.str_to_float(value)

        if action == 'update':
            self.price[0] = value
        elif action == 'insert':
            self.price.insert(0, value)

        return value

    async def read_ohlc(self, insert_fields=None, update_fields=None):
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

        # Defining [ohlc]
        ohlc = ohlc.split(' ')
        o = utils.str_to_float(ohlc[0][1:])
        h = utils.str_to_float(ohlc[1][1:])
        l = utils.str_to_float(ohlc[2][1:])
        c = utils.str_to_float(ohlc[3][1:])

        # Defining [change]
        if len(self.close) > 0:
            change = round(c - self.close[0], 6)
        else:
            change = None

        if update_fields:
            for field in update_fields:
                if field.lower() == 'open':
                    self.open[0] = o
                elif field.lower() == 'high':
                    self.high[0] = h
                elif field.lower() == 'low':
                    self.low[0] = l
                elif field.lower() == 'close':
                    self.close[0] = c
                    if change:
                        self.change[0] = change

        if insert_fields:
            for field in insert_fields:
                if field.lower() == 'open':
                    self.open.insert(0, o)
                elif field.lower() == 'high':
                    self.high.insert(0, h)
                elif field.lower() == 'low':
                    self.low.insert(0, l)
                elif field.lower() == 'close':
                    self.close.insert(0, c)
                    if change:
                        self.change.insert(0, change)

        return [o, h, l, c]

    async def read_ema_50(self, action=None):
        element_id = 'ema_50'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = utils.str_to_float(value)

        if action == 'update':
            self.ema_50[0] = value
        elif action == 'insert':
            self.ema_50.insert(0, value)

        return value

    async def read_ema_21(self, action=None):
        element_id = 'ema_21'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = utils.str_to_float(value)

        if action == 'update':
            self.ema_21[0] = value
        elif action == 'insert':
            self.ema_21.insert(0, value)

        return value

    async def read_ema_9(self, action=None):
        element_id = 'ema_9'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        value = utils.str_to_float(value)

        if action == 'update':
            self.ema_9[0] = value
        elif action == 'insert':
            self.ema_9.insert(0, value)

        return value

    async def read_rsi(self, action=None):
        element_id = 'rsi'
        value = self.ocr_read_element(zone_id=self.broker['elements'][element_id]['zone'],
                                      element_id=element_id,
                                      type=self.broker['elements'][element_id]['type'])
        missing_decimal_separator = True if '.' not in value else False
        value = utils.str_to_float(value)

        if missing_decimal_separator:
            # It's expected that [trade_size] field will always have 2 decimals
            value = value / 100

        if action == 'update':
            self.rsi[0] = value
        elif action == 'insert':
            self.rsi.insert(0, value)

        return value

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
                element['x'] = zone_region.left + 420
                element['y'] = zone_region.top + 90
            elif element_id == 'btn_indicator_1_settings':
                if platform.system().lower() == 'linux':
                    element['x'] = zone_region.left + 230
                else:
                    element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 132
            elif element_id == 'btn_indicator_2_settings':
                if platform.system().lower() == 'linux':
                    element['x'] = zone_region.left + 230
                else:
                    element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 157
            elif element_id == 'btn_indicator_3_settings':
                if platform.system().lower() == 'linux':
                    element['x'] = zone_region.left + 230
                else:
                    element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 182
            elif element_id == 'btn_rsi_settings':
                if platform.system().lower() == 'linux':
                    element['x'] = zone_region.left + 190
                else:
                    element['x'] = zone_region.left + 175
                element['y'] = zone_region.top + 225
            elif element_id == 'btn_chart_remove_indicators':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 267
            elif element_id == 'btn_chart_settings':
                element['x'] = zone_center_x
                element['y'] = zone_region.top + 355
            elif element_id == 'btn_super_strike':
                element['x'] = zone_region.left + 305
                element['y'] = zone_region.top + 20
            elif element_id == 'btn_activate':
                element['x'] = zone_center_x
                element['y'] = zone_center_y
            elif element_id == 'toggle_expiry_time':
                element['x'] = zone_region.left + 505
                element['y'] = zone_region.top + 20
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
                element['x'] = zone_region.left + 83
                element['y'] = zone_region.top + 280
            elif element_id == 'checkbox_rsi_settings_upper_limit':
                element['x'] = zone_region.left + 30
                element['y'] = zone_region.top + 227
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
                element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 180
            elif element_id == 'input_chart_settings_body_red':
                element['x'] = zone_region.left + 255
                element['y'] = zone_region.top + 180
            elif element_id == 'input_chart_settings_wick_green':
                element['x'] = zone_region.left + 215
                element['y'] = zone_region.top + 280
            elif element_id == 'input_chart_settings_wick_red':
                element['x'] = zone_region.left + 255
                element['y'] = zone_region.top + 280
            elif element_id == 'input_chart_settings_background':
                element['x'] = zone_region.left + 235
                element['y'] = zone_region.top + 95
            elif element_id == 'input_chart_settings_grid_lines_v':
                element['x'] = zone_region.left + 230
                element['y'] = zone_region.top + 180
            elif element_id == 'input_chart_settings_grid_lines_h':
                element['x'] = zone_region.left + 230
                element['y'] = zone_region.top + 230
            elif element_id == 'input_chart_settings_scale_lines':
                element['x'] = zone_region.left + 230
                element['y'] = zone_region.top + 160
            elif element_id == 'input_ema_settings_color':
                element['x'] = zone_region.left + 190
                element['y'] = zone_region.top + 130
            elif element_id == 'input_ema_settings_length':
                element['x'] = zone_region.left + 190
                element['y'] = zone_region.top + 130
            elif element_id == 'input_ema_settings_precision':
                element['x'] = zone_region.left + 190
                element['y'] = zone_region.top + 275
            elif element_id == 'input_rsi_settings_color':
                element['x'] = zone_region.left + 220
                element['y'] = zone_region.top + 130
            elif element_id == 'input_rsi_settings_length':
                element['x'] = zone_region.left + 190
                element['y'] = zone_region.top + 130
            elif element_id == 'input_url':
                element['x'] = zone_region.left + zone_region.width + 50
                element['y'] = zone_center_y
            elif element_id == 'slider_background_opacity':
                element['x'] = zone_region.left + 260
                element['y'] = zone_region.top + 250
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
            exit(0)

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
        sleep(wait_when_done)

    def move_to_element(self, element_id, duration=0.0, wait_when_done=0.0):
        element = self.get_element(element_id=element_id)
        pyautogui.moveTo(x=element['x'],
                         y=element['y'],
                         duration=duration)
        sleep(wait_when_done)

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
                        waiting_time = random.randrange(1000, 5000) / 1000
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
            raise RuntimeError(f'Playbook [{playbook_id}] not found.')

        # Clicking on Neutral Area
        self.mouse_event_on_neutral_area(event='click', area_id='bellow_app')

        self.is_automation_running = False
        return result

    def playbook_open_browser(self):
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
            DETACHED_PROCESS = 0x00000008

            # Converting args into [str]
            str_args = ''
            for arg in args:
                str_args += f'{arg} '

            # Executing subprocess
            p = subprocess.Popen(f'"{settings.PATH_BROWSER}" {str_args}',
                                 shell=False,
                                 creationflags=DETACHED_PROCESS).pid
        elif platform.system().lower() == 'linux':
            # Adding [PATH_BROWSER] to [args] on 1st position
            args.insert(0, settings.PATH_BROWSER)

            # Executing subprocess
            p = subprocess.Popen(args,
                                 shell=False,
                                 stdin=None,
                                 stdout=None,
                                 stderr=None).pid

        # Waiting for browser launching
        sleep(10)

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
            self.click_element(element_id='btn_login_confirm', wait_when_done=10)

            # Waiting for page to load
            sleep(10)

    def playbook_refresh_page(self):
        self.mouse_event_on_neutral_area(event='click', area_id='within_app')
        pyautogui.hotkey('shift', 'f5')

        # Waiting for page to load
        sleep(8)

    def playbook_go_to_url(self, url=None):
        # Cleaning field
        self.click_element(element_id='input_url')
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')

        # Typing URL
        pyautogui.typewrite(url, interval=0.05)

        # Ignore suggestions
        pyautogui.press('delete')

        # Go
        pyautogui.press('enter')

        # Waiting for page to load
        sleep(8)

    def playbook_go_to_trading_page(self):
        # Going to trading page
        trading_url = self.get_trading_url()
        self.playbook_go_to_url(url=trading_url)

    def playbook_sync_clock_with_ntp_server(self, ntp_server='pool.ntp.org'):
        stdout = stderr = None

        if platform.system().lower() == 'windows':
            # not implemented yet
            args = []
            pass

        elif platform.system().lower() == 'linux':
            # Defining [args]
            args = ['psync',
                    '-sync',
                    ntp_server]

            # Executing subprocess
            p = subprocess.Popen(args,
                                 shell=False,
                                 stdin=None,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            # Waiting for results
            stdout, stderr = p.communicate()
            stdout, stderr = stdout.decode(), stderr.decode()

        return [stdout, stderr]

    def playbook_tv_reset(self):
        # Reseting chart
        self.playbook_tv_reset_chart()

        # Removing all indicators
        self.playbook_tv_remove_all_indicators()

    def playbook_tv_reset_chart(self):
        # Reseting chart
        self.click_element(element_id='area_chart_background', duration=0.400)
        pyautogui.hotkey('alt', 'r')

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

        # Adding EMAs
        self.playbook_tv_add_indicator(hint='Moving Average Exponential')
        self.playbook_tv_add_indicator(hint='Moving Average Exponential')
        self.playbook_tv_add_indicator(hint='Moving Average Exponential')

        # Configuring EMAs
        self.playbok_tv_configure_indicator_ema(i_indicator=1, length=50)
        self.playbok_tv_configure_indicator_ema(i_indicator=2, length=21)
        self.playbok_tv_configure_indicator_ema(i_indicator=3, length=9)

        # Defining RSI
        self.playbook_tv_add_indicator(hint='Relative Strength Index')
        self.playbok_tv_configure_indicator_rsi(length=2)

    def playbook_tv_set_chart_settings(self, candle_opacity=0, scale_lines_color='white'):
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

        # [tab4] Moving to the scrollable area
        self.move_to_element(element_id='input_chart_settings_grid_lines_h')
        # [tab4] Scrolling down
        if platform.system().lower() == 'linux':
            scroll_clicks = -3
        else:
            scroll_clicks = -430
        pyautogui.scroll(scroll_clicks)
        sleep(0.300)

        # [tab4] Setting [scale_lines] color
        self.click_element(element_id='input_chart_settings_scale_lines', wait_when_done=0.300)
        self.click_element(element_id=f'item_color_{scale_lines_color}')
        self.click_element(element_id='input_color_opacity', clicks=2)
        pyautogui.typewrite('100')
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
        pyautogui.press('escape')

        # Clicking on Neutral Area
        self.mouse_event_on_neutral_area(event='click', area_id='bellow_app')

    def playbok_tv_configure_indicator_ema(self, i_indicator, length, color='white', opacity=0, precision=5):
        # Opening Settings
        self.click_element(element_id=f'btn_indicator_{i_indicator}_settings', wait_when_done=0.300)

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

        # [tab1]
        self.click_element(element_id='navitem_ema_settings_tab1', wait_when_done=0.300)

        # Leaving Settings and Selection
        pyautogui.press(['escape', 'escape'], interval=0.100)

    def playbok_tv_configure_indicator_rsi(self, length, color='black', opacity=0):
        # Opening Settings
        self.click_element(element_id='btn_rsi_settings', wait_when_done=0.300)

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

        # [tab2] Toggle [middle_limit]
        pyautogui.press('tab')
        pyautogui.press('space')

        # [tab2] Toggle [lower_limit]
        pyautogui.press('tab')
        pyautogui.press('space')

        # [tab2] Toggle [hlines_bg]
        pyautogui.press('tab')
        pyautogui.press('space')

        # [tab1]
        self.click_element(element_id='navitem_rsi_settings_tab1', wait_when_done=0.300)

        # Leaving Settings and Selection
        pyautogui.press(['escape', 'escape'], interval=0.100)

    def playbook_set_trade_size(self, trade_size):
        if self.trade_size != trade_size:
            self.click_element(element_id='trade_size', clicks=2)
            pyautogui.typewrite("%.2f" % trade_size)

    def playbook_set_expiry_time(self, expiry_time='05:00'):
        self.click_element(element_id='btn_expiry_time', wait_when_done=0.700)

        if expiry_time == '01:00':
            self.click_element(element_id='dp_item_1min')
        elif expiry_time == '05:00':
            self.click_element(element_id='dp_item_5min')
        else:
            # Option is not supported. Closing dropdown menu
            pyautogui.press('escape')

        # Waiting CSS components
        sleep(0.500)

    def playbook_toggle_expiry_time(self):
        self.click_element(element_id='toggle_expiry_time', wait_when_done=0.250)

    def playbook_activate_super_strike(self):
        # Activationg [super_Strike] mode
        self.click_element(element_id='btn_super_strike', wait_when_done=2)

        # Using the keyboard to get to [btn_activate] (click_element didn't work on Ubuntu)

        # Clicking [input_url]
        self.click_element(element_id='input_url', wait_when_done=0.250)

        # Moving to [btn_activate]
        pyautogui.hotkey('shift', 'tab')
        pyautogui.hotkey('shift', 'tab')
        if platform.system().lower() == 'windows':
            # An extra SHIFT-TAB
            pyautogui.hotkey('shift', 'tab')

        # Toggling [btn_activate]
        pyautogui.press('space')

        # Leaving [super_strike] menu
        self.mouse_event_on_neutral_area(event='click', area_id='screen_center_25')
        sleep(0.500)

    def playbook_move_to_candle(self, i_candle):
        # Defining [x_last_candle] and [candle_width] based on system (or font used)
        zone_id = 'area_bottom_right_conner'
        chart_conner = self.get_zone_region(context_id='tv',
                                            zone_id=zone_id,
                                            confidence=0.95)

        x_candle_0_center = chart_conner.left - 63

        if platform.system().lower() == 'linux':
            candle_width = 6
        else:
            candle_width = 5

        area_chart_background = self.get_element(element_id='area_chart_background')
        y = area_chart_background['y']

        x_candle = x_candle_0_center - (candle_width * i_candle)
        pyautogui.moveTo(x=x_candle, y=y)

        # Trial: Give it some time for CSS loading
        sleep(0.250)

    def playbook_read_previous_candles(self, amount_candles=1):
        action = 'update'
        ohcl_to_insert = None
        ohcl_to_update = ['open', 'high', 'low', 'close']

        # Reseting chart (zooms and deslocation)
        self.playbook_tv_reset_chart()

        if len(self.datetime) < amount_candles:
            # It's going to be the first time we'll have that amount of data
            self.reset_chart_data()
            action = 'insert'
            ohcl_to_insert = ['open', 'high', 'low', 'close']
            ohcl_to_update = None

        for i_candle in range(amount_candles, 0, -1):
            # Reverse iteration from candle X to latest candle
            self.playbook_move_to_candle(i_candle=i_candle)

            # Calculating candle's [datetime]
            now = datetime.utcnow()
            if now.second > settings.CHART_DATA_MIN_SECONDS:
                candle_datetime = now - timedelta(seconds=now.second)
            else:
                candle_datetime = now - timedelta(minutes=1, seconds=now.second)

            self.read_element(element_id='ohlc',
                              insert_fields=ohcl_to_insert,
                              update_fields=ohcl_to_update),
            self.read_element(element_id='ema_50', action=action),
            self.read_element(element_id='ema_21', action=action),
            self.read_element(element_id='ema_9', action=action),
            self.read_element(element_id='rsi', action=action)

            if action == 'insert':
                self.datetime.insert(0, candle_datetime.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Not updating datetime for now...
                pass

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

    def send_chart_data(self):
        if len(self.datetime) < 2:
            # Not enough data yet
            return None

        asset = self.get_asset_for_url_path()
        request_url = settings.LOSS_MANAGEMENT_SERVER_ADDRESS + f'/api/chart_data/{asset}/'
        headers = {'api_key': settings.LOSS_MANAGEMENT_SERVER_API_KEY}

        data = {'datetime': self.datetime[1],
                'open': self.open[1],
                'high': self.high[1],
                'low': self.low[1],
                'close': self.close[1],
                'change': self.change[0] or None,
                'price': self.price[0],
                'ema_50': self.ema_50[1],
                'ema_21': self.ema_21[1],
                'ema_9': self.ema_9[1],
                'rsi': self.rsi[1]}

        try:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)
        except requests.exceptions.Timeout:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)

    ''' Loss Management '''

    def loss_management_sync(self):
        asset = self.get_asset_for_url_path()

        request_url = settings.LOSS_MANAGEMENT_SERVER_ADDRESS + f'/api/loss_management/{asset}/sync/'
        headers = {'api_key': settings.LOSS_MANAGEMENT_SERVER_API_KEY}
        data = {
            'highest_balance': self.highest_balance,
            'payout': self.payout
        }

        try:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)
        except requests.exceptions.Timeout:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)
        r = json.loads(r.text)

        for k, v in r.items():
            if hasattr(self, k):
                setattr(self, k, v)

        if r['is_stop_loss_triggered']:
            msg = (f"{tmsg.danger}[ERROR]{tmsg.endc} "
                   f"{tmsg.italic}- This asset has reached Stop Loss."
                   f"\n\t  - The cumulative loss is [{self.cumulative_loss} USD]."
                   f"\n\n"
                   f"\t  - I think I'm done for today.{tmsg.endc}")
            tmsg.input(msg=msg, clear=True)
        elif r['is_stop_gain_triggered']:
            msg = (f"{tmsg.success}[GAIN]{tmsg.endc} "
                   f"{tmsg.italic}- Time to celebrate."
                   f"\n\t  - Today we got a gain of [{self.cumulative_loss} USD]. That means "
                   f"\n\n"
                   f"\t  - I think I'm done for today.{tmsg.endc}")
            tmsg.input(msg=msg, clear=True)

    def loss_management_close_trade(self, strategy_id, result=None, trade_size=0.00):
        asset = self.get_asset_for_url_path()

        request_url = settings.LOSS_MANAGEMENT_SERVER_ADDRESS + f'/api/loss_management/{asset}/close_trade/'
        headers = {'api_key': settings.LOSS_MANAGEMENT_SERVER_API_KEY}
        data = {
            'strategy_id': strategy_id,
            'initial_trade_size': self.initial_trade_size,
            'trade_size': trade_size,
            'trade_result': result,
            'balance_trade_size_percent': settings.BALANCE_TRADE_SIZE_PERCENT
        }

        try:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)
        except requests.exceptions.Timeout:
            r = requests.post(url=request_url,
                              headers=headers,
                              json=data)
        r = json.loads(r.text)

        # Updating [loss_management] data
        for k, v in r.items():
            if hasattr(self, k):
                setattr(self, k, v)

    ''' TA & Trading '''

    def get_optimal_trade_size(self):
        balance_trade_size = self.highest_balance * settings.BALANCE_TRADE_SIZE_PERCENT

        if self.recovery_mode:
            # [recovery_mode] is activated
            optimal_trade_size = self.recovery_trade_size

        elif self.initial_trade_size > balance_trade_size:
            # [initial_trade_size] is greater than [balance_trade_size]
            # Which means [highest_balance] is lesser than 400 USD
            optimal_trade_size = self.initial_trade_size

        else:
            # [balance_trade_size] is the optimal choice
            optimal_trade_size = balance_trade_size

        return round(optimal_trade_size, 2)

    def get_martingale_trade_size(self, i_trade=1, last_trade_size=0.00):
        # Retrieving the [multiplier] based on [settings.MARTINGALE_STRATEGY]
        martingale_multiplier = settings.MARTINGALE_STRATEGY[i_trade]

        # Calculating [trade_size] based on current [payout]
        trade_size = last_trade_size / (self.payout / 100) * martingale_multiplier
        return trade_size

    async def open_position(self, strategy_id, side, trade_size, stop_loss=None):
        position = {'result': None,
                    'asset': self.asset,
                    'strategy_id': strategy_id,
                    'side': side,
                    'stop_loss': stop_loss,
                    'trades': []}

        self.ongoing_positions[strategy_id] = position
        await self.open_trade(strategy_id=strategy_id, side=side, trade_size=trade_size)

        return position

    async def close_position(self, strategy_id, result):
        # Closing trade and position
        await self.close_trade(strategy_id=strategy_id, result=result)
        self.ongoing_positions[strategy_id]['result'] = result
        closed_position = self.ongoing_positions[strategy_id].copy()

        # [positions.csv] Appending data to [positions.csv] file
        positions_file = os.path.join(settings.PATH_DATA, 'positions.csv')
        df = self.df_ongoing_positions()
        positions = df.query(f'Strategy == "{strategy_id}"')
        positions.to_csv(positions_file, mode='a', index=False, header=False)

        self.position_history.append(self.ongoing_positions[strategy_id].copy())
        self.ongoing_positions.pop(strategy_id)

        return closed_position

    async def open_trade(self, strategy_id, side, trade_size):
        # Running concurrently
        await asyncio.gather(
            self.execute_playbook(playbook_id='open_trade', side=side, trade_size=trade_size),
            self.read_element(element_id='price', is_async=True, action='update')
        )

        now = datetime.utcnow()
        expiration_time = now + timedelta(minutes=int(self.expiry_time[:2]),
                                          seconds=int(self.expiry_time[-2:]))
        trade = {
            'open_time': now,
            'expiration_time': expiration_time,
            'trade_size': trade_size,
            'open_price': self.price[0],
            'result': None
        }

        self.ongoing_positions[strategy_id]['trades'].append(trade)
        return trade

    async def close_trade(self, strategy_id, result):
        position = self.ongoing_positions[strategy_id]
        trade = position['trades'][-1]
        trade['result'] = result

        # [Loss Management] Updating [cumulative_loss]
        self.loss_management_close_trade(strategy_id=strategy_id,
                                         result=result,
                                         trade_size=trade['trade_size'])

        return position['trades'][-1]

    def start(self):
        msg = "Validating\n"
        tmsg.print(context='Warming Up!', msg=msg, clear=True)

        refresh_page_countdown = settings.REFRESH_PAGE_EVERY_MINUTES

        long_action_lock_file = os.path.join(settings.PATH_LOCK,
                                             f'{settings.LOCK_LONG_ACTION_FILENAME}{settings.LOCK_FILE_EXTENSION}')

        self.run_validation()

        # Reading last 10 candles PB
        msg = "Reading previous 7 candles"
        if not os.path.exists(long_action_lock_file):
            for item in utils.progress_bar([0], prefix=msg):
                self.execute_playbook(playbook_id='read_previous_candles', amount_candles=7)

        # First run using estimated time (1.5 seconds)
        reading_chart_duration = default_reading_duration = timedelta(seconds=0.750).total_seconds()
        lookup_trigger = 60 - default_reading_duration

        while True:
            context = 'Trading' if self.ongoing_positions else 'Getting Ready'
            tmsg.print(context=context, clear=True)

            # Calculating [lookup_trigger]: average with last value
            lookup_trigger = (lookup_trigger + (60 - reading_chart_duration)) / 2

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

            if str(self.agent_id).endswith('1'):
                validation_trigger = 10
            elif str(self.agent_id).endswith('2'):
                validation_trigger = 27.5
            else:
                validation_trigger = 42.5

            # Waiting PB
            msg = "Watching Price Action"
            if validation_trigger > utils.now_seconds():
                diff_sec = validation_trigger - utils.now_seconds()
                lookup_time_threshold = datetime.now() + \
                                        timedelta(seconds=lookup_trigger - utils.now_seconds())
            else:
                diff_sec = validation_trigger - utils.now_seconds() + 60
                lookup_time_threshold = datetime.now() + \
                                        timedelta(seconds=lookup_trigger - utils.now_seconds()) + \
                                        timedelta(seconds=60)

            items = range(0, int(diff_sec * 1 / settings.PROGRESS_BAR_INTERVAL_TIME))
            for item in utils.progress_bar(items, prefix=msg, reverse=True):
                sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

            # Checking token (only if mouse/keyboard are not being used)
            if not os.path.exists(long_action_lock_file) and len(self.ongoing_positions) == 0:
                # Focusing on App
                self.mouse_event_on_neutral_area(event='click', area_id='within_app')
                sleep(1)
                if self.is_alerting_session_ended():
                    # Alert 401 popping up... Session expired.
                    msg = "Session expired... Refreshing page"
                    for item in utils.progress_bar([0], prefix=msg):
                        self.execute_playbook(playbook_id='go_to_trading_page')
                        refresh_page_countdown = settings.REFRESH_PAGE_EVERY_MINUTES

                elif refresh_page_countdown <= 0:
                    # [bug-fix] Refreshing page here
                    # It prevents chart to show wrong data (flat candles, clock delay)
                    msg = "Refreshing page"
                    for item in utils.progress_bar([0], prefix=msg):
                        self.execute_playbook(playbook_id='refresh_page')
                        refresh_page_countdown = settings.REFRESH_PAGE_EVERY_MINUTES

            # Validation PB
            msg = "Quick validation"
            for item in utils.progress_bar([0], prefix=msg):
                self.run_validation()

            # Last candle data PB
            msg = "Reading previous candle's data"
            if not os.path.exists(long_action_lock_file):
                for item in utils.progress_bar([0], prefix=msg):
                    self.execute_playbook(playbook_id='read_previous_candles', amount_candles=1)

            if datetime.now() < lookup_time_threshold:
                # Ready for Trading

                # Waiting PB
                msg = "Watching candle closure"
                diff_sec = lookup_trigger - utils.now_seconds()

                items = range(0, int(diff_sec / settings.PROGRESS_BAR_INTERVAL_TIME))
                for item in utils.progress_bar(items, prefix=msg, reverse=True):
                    sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                # Running Lookup
                result = asyncio.run(self.strategies_lookup(context=context))
                reading_chart_duration = result['reading_chart_duration']

                # Checking if [lookup] is taking too long
                if self.is_reading_taking_too_long(element_id='chart_data',
                                                   duration=reading_chart_duration):
                    # Waiting PB
                    msg = "Reseting Lookup Trigger (CTRL + C to cancel)"
                    wait_secs = 5
                    items = range(0, int(wait_secs / settings.PROGRESS_BAR_INTERVAL_TIME))
                    for item in utils.progress_bar(items, prefix=msg, reverse=True):
                        sleep(settings.PROGRESS_BAR_INTERVAL_TIME)

                    # Reseting [reading_chart_duration]
                    reading_chart_duration = default_reading_duration

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

                self.send_chart_data()

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

                # Reseting [reading_chart_duration]
                reading_chart_duration = default_reading_duration

                waiting_time = 5
                sleep(waiting_time)

            refresh_page_countdown -= 1

    async def strategies_lookup(self, context):
        msg = "Applying strategies"
        result = {'reading_chart_duration': None}

        # Defining [strategies]
        strategies = settings.TRADING_STRATEGIES.copy()

        # Reading [close] and [rsi]
        start = datetime.now()

        element_ids = ['price']
        ohlc_insert_fields = ['open', 'high', 'low', 'close']
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.read_chart_data(element_ids=element_ids))
            tg.create_task(self.read_element(element_id='ohlc',
                                             is_async=True,
                                             insert_fields=ohlc_insert_fields))
        # await self.read_chart_data(element_ids=element_ids)

        delta = datetime.now() - start
        result['reading_chart_duration'] = delta.total_seconds()

        print(f'reading_chart_duration: {result["reading_chart_duration"]}')

        # Retrieving optimal [trade_size]
        trade_size = self.get_optimal_trade_size()

        # Executing tasks
        tasks = []
        start = datetime.now()
        async with asyncio.TaskGroup() as tg:
            for strategy in utils.progress_bar(strategies, prefix=msg):
                f_strategy = f"strategy_{strategy}"

                if hasattr(self, f_strategy) and callable(strategy := getattr(self, f_strategy)):
                    tasks.append(tg.create_task(strategy(trade_size=trade_size)))
                else:
                    # Strategy not found
                    msg = (f"{utils.tmsg.danger}[ERROR]{utils.tmsg.endc} "
                           f"- That's embarrassing. :/ "
                           f"\n\t- I couldn't find a function for strategy [{strategy}].! :/"
                           f"\n\t- Can you call the human, please? I think he can fix it... {utils.tmsg.endc}")
                    tmsg.input(msg=msg, clear=True)
                    raise RuntimeError(f'Strategy [{strategy}] not found.')
        delta = datetime.now() - start
        result['lookup_duration'] = delta.total_seconds()

        print(f'lookup_duration: {result["lookup_duration"]}')

        # Reading [ema]
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.read_element(element_id='ema_50', is_async=True, action='insert'))
            tg.create_task(self.read_element(element_id='ema_21', is_async=True, action='insert'))
            tg.create_task(self.read_element(element_id='ema_9', is_async=True, action='insert'))

        if len(self.ongoing_positions) == 0:
            # There are no open positions
            for task in tasks:
                position = task.result()

                if position and position['result']:
                    # Position has been closed
                    tmsg.print(context=context, clear=True)
                    art.tprint(text=position['result'], font='block')
                    await asyncio.sleep(2)

        return result

    async def strategy_ema_rsi_8020(self):
        strategy_id = 'ema_rsi_8020'

        if strategy_id in self.ongoing_positions:
            position = self.ongoing_positions[strategy_id]
        else:
            position = None

        if position:
            # Has position open
            result = None
            first_trade = position['trades'][0]
            last_trade = position['trades'][-1]
            amount_trades = len(position['trades'])

            # Defining [expiration_countdown]
            now = datetime.utcnow()
            expiration_countdown = first_trade['expiration_time'] - now

            if expiration_countdown < timedelta(seconds=10):
                # Trade is about to expire

                if position['side'] == 'up':
                    # up
                    if self.price[0] > last_trade['open_price']:
                        result = 'gain'
                    elif self.price[0] < last_trade['open_price']:
                        result = 'loss'
                    else:
                        result = 'draw'

                else:
                    # down
                    if self.price[0] < last_trade['open_price']:
                        result = 'gain'
                    elif self.price[0] > last_trade['open_price']:
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

                    elif position['side'] == 'up':
                        if self.rsi[0] < 20:
                            # Abort it
                            position = await self.close_position(strategy_id=strategy_id,
                                                                 result=result)
                    elif position['side'] == 'down':
                        if self.rsi[0] > 80:
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
                            trade_size = self.get_martingale_trade_size(i_trade=amount_trades,
                                                                        last_trade_size=last_trade['trade_size'])

                        await self.open_trade(strategy_id=strategy_id,
                                              side=position['side'],
                                              trade_size=trade_size)
                else:
                    # Draw
                    if amount_trades == 1:
                        # Draw on first trade
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)
                    else:
                        await self.close_trade(strategy_id=strategy_id,
                                               result=result)
                        await self.open_trade(strategy_id=strategy_id,
                                              side=position['side'],
                                              trade_size=last_trade['trade_size'])

        else:
            # No open position

            if len(self.datetime) >= 3:
                dst_price_ema = utils.distance_percent_abs(v1=self.close[1], v2=self.ema_50[0])

                trade_size = self.get_optimal_trade_size()

                if min(self.close[:5]) > self.ema_50[0]:
                    # Price has been above [ema]
                    if dst_price_ema < 0.0001618:
                        # Price is close to [ema]: Trend continuation
                        if self.rsi[1] <= 20 and 40 <= self.rsi[0] <= 80:
                            position = await self.open_position(strategy_id=strategy_id,
                                                                side='up',
                                                                trade_size=trade_size)

                elif max(self.close[:5]) < self.ema_50[0]:
                    # Price has been bellow [ema]
                    if dst_price_ema < 0.0001618:
                        # Price is close to [ema]: Trend continuation
                        if self.rsi[1] >= 80 and 60 >= self.rsi[0] >= 20:
                            position = await self.open_position(strategy_id=strategy_id,
                                                                side='down',
                                                                trade_size=trade_size)
        return position

    async def strategy_ema_rsi_8020_contrarian(self):
        strategy_id = 'ema_rsi_8020_contrarian'

        if strategy_id in self.ongoing_positions:
            position = self.ongoing_positions[strategy_id]
        else:
            position = None

        if position:
            # Has position open
            result = None
            first_trade = position['trades'][0]
            last_trade = position['trades'][-1]
            amount_trades = len(position['trades'])

            # Defining [expiration_countdown]
            now = datetime.utcnow()
            expiration_countdown = first_trade['expiration_time'] - now

            if expiration_countdown < timedelta(seconds=10):
                # Trade is about to expire

                if position['side'] == 'up':
                    # up
                    if self.price[0] > last_trade['open_price']:
                        result = 'gain'
                    elif self.price[0] < last_trade['open_price']:
                        result = 'loss'
                    else:
                        result = 'draw'

                else:
                    # down
                    if self.price[0] < last_trade['open_price']:
                        result = 'gain'
                    elif self.price[0] > last_trade['open_price']:
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

                    elif position['side'] == 'up':
                        if self.rsi[0] < 20:
                            # Abort it
                            position = await self.close_position(strategy_id=strategy_id,
                                                                 result=result)
                    elif position['side'] == 'down':
                        if self.rsi[0] > 80:
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
                            trade_size = self.get_martingale_trade_size(i_trade=amount_trades,
                                                                        last_trade_size=last_trade['trade_size'])

                        await self.open_trade(strategy_id=strategy_id,
                                              side=position['side'],
                                              trade_size=trade_size)
                else:
                    # Draw
                    if amount_trades == 1:
                        # Draw on first trade
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)
                    else:
                        await self.close_trade(strategy_id=strategy_id,
                                               result=result)
                        await self.open_trade(strategy_id=strategy_id,
                                              side=position['side'],
                                              trade_size=last_trade['trade_size'])

        else:
            # No open position

            if len(self.datetime) >= 3:
                dst_price_ema = utils.distance_percent_abs(v1=self.close[1], v2=self.ema_50[0])

                trade_size = self.get_optimal_trade_size()

                if min(self.close[:5]) > self.ema_50[0]:
                    # Price has been above [ema]
                    if dst_price_ema > 0.001200:
                        # Price is too far from [ema]: Contrarian
                        if self.rsi[1] >= 80 and 70 >= self.rsi[0] >= 20:
                            position = await self.open_position(strategy_id=strategy_id,
                                                                side='down',
                                                                trade_size=trade_size)

                elif max(self.close[:5]) < self.ema_50[0]:
                    # Price has been bellow [ema]
                    if dst_price_ema > 0.001200:
                        # Price is far from [ema]: Contrarian
                        if self.rsi[1] <= 20 and 30 <= self.rsi[0] <= 80:
                            position = await self.open_position(strategy_id=strategy_id,
                                                                side='up',
                                                                trade_size=trade_size)
        return position

    async def strategy_ema_9_1(self, trade_size):
        strategy_id = 'ema_9_1'

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
                if self.price[0] > last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] < last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

                # Defining [stop_loss]
                if amount_trades == 1:
                    position['stop_loss'] = self.low[1]

            else:
                # down
                if self.price[0] < last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] > last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

                # Defining [stop_loss]
                if amount_trades == 1:
                    position['stop_loss'] = self.high[2]

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
                    if self.close[0] < position['stop_loss']:
                        # [close] reached [stop_loss]
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)

                elif position['side'] == 'down':
                    if self.close[0] > position['stop_loss']:
                        # [close] reached [stop_loss]
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
                        trade_size = self.get_martingale_trade_size(i_trade=amount_trades,
                                                                    last_trade_size=last_trade['trade_size'])

                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=trade_size)
            else:
                # Draw
                if amount_trades == 1:
                    # Draw on first trade
                    # Abort it
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)
                else:
                    await self.close_trade(strategy_id=strategy_id,
                                           result=result)
                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=last_trade['trade_size'])

        if position is None or position['result']:
            # No open position
            i_candle = 1
            min_candles = 7
            crossed_up = crossed_down = is_setup_confirmed = None

            if len(self.datetime) >= min_candles + i_candle:
                # We got enough candles
                if self.close[2] < self.ema_9[1] < self.close[1]:
                    crossed_up = True
                elif self.close[2] > self.ema_9[1] > self.close[1]:
                    crossed_down = True

                if crossed_up:
                    # Price  crosssed [ema_9] up

                    if self.close[0] > self.high[1]:
                        # Price broke last candle's high

                        for i in range(i_candle, min_candles + i_candle):
                            if self.close[i] < self.ema_9[i - 1]:
                                if i == min_candles + i_candle - 1:
                                    # [close] has been bellow [ema_9] for a while
                                    is_setup_confirmed = True
                            else:
                                # Aborting
                                break

                elif crossed_down:
                    # Price crosssed [ema_9] down

                    if self.close[0] < self.low[1]:
                        # Price broke last candle's low

                        for i in range(i_candle, min_candles + i_candle):
                            if self.close[i] > self.ema_9[i - 1]:
                                if i == min_candles + i_candle - 1:
                                    # [close] has been above [ema_9] for a while
                                    is_setup_confirmed = True
                            else:
                                # Aborting
                                break

                if is_setup_confirmed:
                    # Setup has been confirmed
                    if crossed_up:
                        side = 'up'
                    else:
                        side = 'down'

                    # Opening position
                    position = await self.open_position(strategy_id=strategy_id,
                                                        side=side,
                                                        trade_size=trade_size)
        return position

    async def strategy_ema_9_2_3(self, trade_size):
        strategy_id = 'ema_9_2_3'

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
                if self.price[0] > last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] < last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.price[0] < last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] > last_trade['open_price']:
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
                    if self.close[0] < position['stop_loss']:
                        # [close] reached [stop_loss]
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)

                elif position['side'] == 'down':
                    if self.close[0] > position['stop_loss']:
                        # [close] reached [stop_loss]
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
                        trade_size = self.get_martingale_trade_size(i_trade=amount_trades,
                                                                    last_trade_size=last_trade['trade_size'])

                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=trade_size)
            else:
                # Draw
                if amount_trades == 1:
                    # Draw on first trade
                    # Abort it
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)
                else:
                    await self.close_trade(strategy_id=strategy_id,
                                           result=result)
                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=last_trade['trade_size'])

        if position is None or position['result']:
            # No open position
            i_candle = 1
            min_candles = 3
            side = stop_loss = is_setup_confirmed = None

            # Add [ema_50] as ref?

            if len(self.datetime) >= min_candles + i_candle:
                # We got enough candles

                dst_ema_9_close_1 = utils.distance_percent_abs(v1=self.ema_9[0], v2=self.close[1])

                if self.close[0] > self.ema_9[0] > self.ema_50[0]:
                    # Price is above [ema_9]
                    # [ema_50] giving support
                    side = 'up'

                    if dst_ema_9_close_1 < 0.0001618:
                        # Price is close to [ema_9]

                        if min(self.change[:3]) < 0:
                            # At least 1 red candle found

                            if self.close[0] > self.high[1] and self.high[1] < self.high[2]:
                                # Price confirmed a pivot up

                                for i in range(i_candle, min_candles + i_candle):
                                    if self.close[i] > self.ema_9[i - 1]:
                                        if i == min_candles + i_candle - 1:
                                            # [close] has been above [ema_9] for a while
                                            is_setup_confirmed = True
                                            stop_loss = self.low[1]
                                    else:
                                        # Aborting
                                        break

                elif self.close[0] < self.ema_9[0] < self.ema_50[0]:
                    # Price is bellow [ema_9]
                    # [ema_50] giving support
                    side = 'down'

                    if dst_ema_9_close_1 < 0.0001618:
                        # Price is closed to [ema_9]

                        if max(self.change[:3]) > 0:
                            # At least 1 green candle found

                            if self.close[0] < self.low[1] and self.low[1] > self.low[2]:
                                # Price confirmed a pivot down

                                for i in range(i_candle, min_candles + i_candle):
                                    if self.close[i] < self.ema_9[i - 1]:
                                        if i == min_candles + i_candle - 1:
                                            # [close] has been bellow [ema_9] for a while
                                            is_setup_confirmed = True
                                            stop_loss = self.high[1]
                                    else:
                                        # Aborting
                                        break

                if is_setup_confirmed:
                    # Setup has been confirmed
                    position = await self.open_position(strategy_id=strategy_id,
                                                        side=side,
                                                        trade_size=trade_size,
                                                        stop_loss=stop_loss)

        return position

    async def strategy_ema_9_4(self, trade_size):
        strategy_id = 'ema_9_4'

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
                if self.price[0] > last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] < last_trade['open_price']:
                    result = 'loss'
                else:
                    result = 'draw'

            else:
                # down
                if self.price[0] < last_trade['open_price']:
                    result = 'gain'
                elif self.price[0] > last_trade['open_price']:
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
                    if self.close[0] < position['stop_loss']:
                        # [close] reached [stop_loss]
                        # Abort it
                        position = await self.close_position(strategy_id=strategy_id,
                                                             result=result)

                elif position['side'] == 'down':
                    if self.close[0] > position['stop_loss']:
                        # [close] reached [stop_loss]
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
                        trade_size = self.get_martingale_trade_size(i_trade=amount_trades,
                                                                    last_trade_size=last_trade['trade_size'])

                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=trade_size)
            else:
                # Draw
                if amount_trades == 1:
                    # Draw on first trade
                    # Abort it
                    position = await self.close_position(strategy_id=strategy_id,
                                                         result=result)
                else:
                    await self.close_trade(strategy_id=strategy_id,
                                           result=result)
                    await self.open_trade(strategy_id=strategy_id,
                                          side=position['side'],
                                          trade_size=last_trade['trade_size'])

        if position is None or position['result']:
            # No open position
            i_candle = 3
            min_candles = 4
            side = stop_loss = crossing_up = crossing_down = is_setup_confirmed = None

            if len(self.datetime) >= min_candles + i_candle:
                # We got enough candles

                if self.ema_9[1] > self.ema_50[1] and self.close[2] < self.ema_9[1] < self.close[1]:
                    crossing_up = True

                elif self.ema_9[1] < self.ema_50[1] and self.close[2] > self.ema_9[1] > self.close[1]:
                    crossing_down = True

                if crossing_up:
                    side = 'up'

                    if self.close[0] > self.high[1]:
                        # Price broke last [high]

                        for i in range(i_candle, min_candles + i_candle):
                            if self.close[i] > self.ema_9[i - 1]:
                                if i == min_candles + i_candle - 1:
                                    # [close] has been above [ema_9] for a while
                                    is_setup_confirmed = True
                                    stop_loss = self.low[2]
                            else:
                                # Aborting
                                break

                elif crossing_down:
                    side = 'down'

                    if self.close[0] < self.low[1]:
                        # Price broke last [low]

                        for i in range(i_candle, min_candles + i_candle):
                            if self.close[i] < self.ema_9[i - 1]:
                                if i == min_candles + i_candle - 1:
                                    # [close] has been bellow [ema_9] for a while
                                    is_setup_confirmed = True
                                    stop_loss = self.high[2]
                            else:
                                # Aborting
                                break

                if is_setup_confirmed:
                    # Setup has been confirmed
                    position = await self.open_position(strategy_id=strategy_id,
                                                        side=side,
                                                        trade_size=trade_size,
                                                        stop_loss=stop_loss)
        return position
