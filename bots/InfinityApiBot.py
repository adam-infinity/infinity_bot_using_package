from collections import deque
from constants import OrderSide as Osi
from constants import RollOverTime as Rot
from constants import Token
import datetime as dt
import logging
import os
from other import InfinityAPIHandler as Inf
from other import MiscHelperFunctions as Mhf
from rest_client import infinity_client
from threading import Thread
from time import sleep
import uuid


def last_rollover_datetime():
    current_utc_datetime = dt.datetime.utcnow()
    if current_utc_datetime.time() > dt.time(Rot.HOUR, Rot.MINUTE, Rot.SECOND):
        date_to_use = current_utc_datetime.date()
    else:
        date_to_use = current_utc_datetime.date() - dt.timedelta(days=1)
    pass
    datetime_to_use = dt.datetime.combine(date_to_use, dt.time(Rot.HOUR, Rot.MINUTE, Rot.SECOND))
    return datetime_to_use.replace(tzinfo=dt.timezone.utc)


class InfinityApiBot:

    def __init__(self, verify, send_orders=True, cancel_orders=True, update_active_orders=True):

        self.cfg = Mhf.load_config_file_etc()
        self.bot_name = 'InfAPIBot'
        self.address = self.cfg['wallet_address']
        # self.wallet_id = XXXX  # TODO - Currently hardcoded. Need to add function in infinity_client.py to get this
        self.chain_id = self.cfg['chainId']
        self.user_agent = self.cfg['user-agent']
        self.domain = self.cfg['infinity_url']
        logging.info(self.domain)
        self.verify = verify
        self.send_orders = send_orders
        self.cancel_orders = cancel_orders

        # New code to handle/use infinity_rest_client
        sys_env = self.domain[8:11]
        match sys_env.lower():
            case 'uat':
                is_prod_env = True  # Technically not correct since UAT isn't PROD
            case 'dev':
                is_prod_env = False
            case _:
                raise Exception('Unrecognized system environment')

        self.inf_rest = infinity_client.Client(
            prod=is_prod_env,
            login=True,
            user_agent=self.user_agent,
            wallet_address=self.address,
            wallet_id=None,  # Ok to leave blank
            chain_id=self.chain_id,
            private_key=os.getenv('PRIVATE_KEY'),
            verify_tls=self.verify,
            logger=None)
        # self.cookies = Inf.login(self.bot_name, self.address, self.chain_id, self.user_agent, self.domain, self.cfg, self.verify)  # TODO - Comment me out
        self.wallets = self.inf_rest.get_user_wallets()['wallets']  # Inf.list_wallets(self.domain, self.cookies, self.verify)
        self.inf_rest._wallet_id = self.get_wallet_id()  # TODO - Do we want this starting with underscore? Do we want to set it within our code?
        self.wallet_details = self.get_trading_wallet_details()  # Inf.list_wallet_details(self.get_wallet_id(), self.domain, self.cookies, self.verify)

        self.floating_markets = None  # result['markets']
        self.floating_tokens_and_prices = None  # result['tokens']
        self.get_floating_markets_tokens_and_prices() # self.floating_markets_old, self.floating_tokens_and_prices_old = Inf.list_floating_rate_markets(self.domain, self.verify)

        self.fixed_markets = None
        self.fixed_markets_last_updated = None
        self.list_all_fixed_rate_markets()
        self.active_floating_orders = {}
        self.active_fixed_orders = {}
        self.ok_to_update_active_orders = update_active_orders
        if self.ok_to_update_active_orders:
            self.update_active_orders()
        self.bid_ask_last_rates = {}
        self.update_bid_ask_last_rates()
        self.cancelled_floating_orders = deque([], maxlen=1000)
        self.cancelled_fixed_orders = deque([], maxlen=10000)

    def cancel_fixed_order(self, order_id):
        if self.cancel_orders:
            if order_id not in self.cancelled_fixed_orders:
                self.cancelled_fixed_orders.append(order_id)
                self.inf_rest.cancel_fixed_rate_order_by_order_id(order_id)  # Inf.cancel_fixed_order(order_id, self.domain, self.cookies, self.verify)

    def cancel_floating_order(self, order_id):
        if self.cancel_orders:
            if order_id not in self.cancelled_floating_orders:
                self.cancelled_floating_orders.append(order_id)
                self.inf_rest.cancel_floating_rate_order_by_order_id(order_id)  # Inf.cancel_floating_order(order_id, self.domain, self.cookies, self.verify)

    def check_if_all_fixed_rate_market_dates_look_ok(self):
        result = True
        for token_id in self.fixed_markets:
            if len(self.fixed_markets[token_id]) > 0:
                for fixed_market in self.fixed_markets[token_id]:
                    this_maturity_date = dt.datetime.utcfromtimestamp(fixed_market['maturityDate']/1000).date()
                    expected_maturity_date =\
                        Mhf.convert_tenor_to_date(
                            str(fixed_market['daysToMaturity']) + 'D',
                            dt.datetime.now(dt.timezone.utc))
                    result = result and this_maturity_date == expected_maturity_date
        return result

    def find_active_orders_by_wallet_and_market(self, market_id=None, floating_only=False, fixed_only=False):
        active_orders = []

        # FLOATING
        if not fixed_only:
            for order in self.active_floating_orders:
                if market_id is None:
                    active_orders.append(order)
                    pass
                else:
                    if order['marketId'] == market_id:
                        active_orders.append(order)
                    pass

        # FIXED
        if not floating_only:
            for order in self.active_fixed_orders:
                if market_id is None:
                    active_orders.append(order)
                    pass
                else:
                    if order['marketId'] == market_id:
                        active_orders.append(order)
                    pass
        return active_orders

    def get_all_floating_and_fixed_order_position_quantities(self):
        borrow_order_positions_by_token = {}
        lend_order_positions_by_token = {}

        borrow_order_positions_by_token, lend_order_positions_by_token = self.process_orders(
            borrow_order_positions_by_token, lend_order_positions_by_token, self.active_floating_orders)
        borrow_order_positions_by_token, lend_order_positions_by_token = self.process_orders(
            borrow_order_positions_by_token, lend_order_positions_by_token, self.active_fixed_orders)

        return borrow_order_positions_by_token, lend_order_positions_by_token

    def get_best_bid_ask(self, token, is_floating_market, days_to_maturity=0, min_bid_n_ask_size=0):
        try:
            token_id = self.get_token_id_from_floating_tokens(token)

            if len(self.bid_ask_last_rates[token_id]) == 0:
                return None, None

            if is_floating_market:
                return float(self.bid_ask_last_rates[token_id]['ir']['bid']), \
                    float(self.bid_ask_last_rates[token_id]['ir']['ask'])
            else:
                while True:
                    i = 0

                    while self.bid_ask_last_rates[token_id]['fr'][i]['daysToMaturity'] < days_to_maturity:
                        i = i + 1

                    if self.bid_ask_last_rates[token_id]['fr'][i]['daysToMaturity'] > days_to_maturity:
                        logging.fatal(f'Error - days to maturity ({days_to_maturity}) not found.')
                        os._exit(1)

                    if 'bid' not in self.bid_ask_last_rates[token_id]['fr'][i]\
                            or 'ask' not in self.bid_ask_last_rates[token_id]['fr'][i]:
                        floating_bid, floating_ask = \
                            self.get_best_bid_ask(token, True, 0, min_bid_n_ask_size)

                    if 'bid' in self.bid_ask_last_rates[token_id]['fr'][i]:
                        bid = float(self.bid_ask_last_rates[token_id]['fr'][i]['bid'])
                    else:
                        if 'ask' in self.bid_ask_last_rates[token_id]['fr'][i]:
                            bid = max(float(
                                self.bid_ask_last_rates[token_id]['fr'][i]['ask']) - 0.0001, 0.0001)
                        else:
                            bid = floating_bid

                    if 'ask' in self.bid_ask_last_rates[token_id]['fr'][i]:
                        ask = float(self.bid_ask_last_rates[token_id]['fr'][i]['ask'])
                    else:
                        if 'bid' in self.bid_ask_last_rates[token_id]['fr'][i]:
                            ask = float(
                                self.bid_ask_last_rates[token_id]['fr'][i]['bid']) + 0.0001
                        else:
                            ask = floating_ask

                    if self.bid_ask_last_rates[token_id]['fr'][i]['daysToMaturity'] == days_to_maturity:
                        return bid, ask

        except Exception as e:
            logging.fatal(f'Error {e} - Cannot get best bid & ask')
            os._exit(1)

    def get_current_positions_and_orders_in_usd(self, token_id):
        token_total_borrow_usd = 0.0
        token_total_lend_usd = 0.0
        wallet_total_borrow_usd = 0.0
        wallet_total_lend_usd = 0.0
        borrow_order_positions, lend_order_positions = \
            self.get_all_floating_and_fixed_order_position_quantities()
        for this_token_id in self.floating_tokens_and_prices:
            if self.floating_tokens_and_prices[this_token_id]['tokenType'] != Token.TOKEN_TYPE_ERC20:
                break
            this_price = float(self.floating_tokens_and_prices[this_token_id]['price'])
            this_borrow_order_position = 0.0
            this_lend_order_position = 0.0
            if self.floating_tokens_and_prices[this_token_id]['code'] in borrow_order_positions:
                this_borrow_order_position = \
                    float(borrow_order_positions[self.floating_tokens_and_prices[this_token_id]['code']])
            if self.floating_tokens_and_prices[this_token_id]['code'] in lend_order_positions:
                this_lend_order_position = \
                    float(lend_order_positions[self.floating_tokens_and_prices[this_token_id]['code']])
            wallet_total_borrow_usd = \
                wallet_total_borrow_usd + max(0.0, this_borrow_order_position) * this_price \
                + this_borrow_order_position * this_price
            wallet_total_lend_usd = \
                wallet_total_lend_usd - min(0.0, this_lend_order_position) * this_price \
                + this_lend_order_position * this_price

            if this_token_id == token_id:
                token_total_borrow_usd = \
                    token_total_borrow_usd + max(0.0, this_borrow_order_position) * this_price \
                    + this_borrow_order_position * this_price
                token_total_lend_usd = \
                    token_total_lend_usd - min(0.0, this_lend_order_position) * this_price \
                    + this_lend_order_position * this_price

        return token_total_borrow_usd, token_total_lend_usd, wallet_total_borrow_usd, wallet_total_lend_usd

    def get_fixed_rate_orders(self, token_id, days_to_maturity):
        market_id = self.get_market_id_etc_from_token_id(token_id, False, days_to_maturity)
        orders = self.find_active_orders_by_wallet_and_market(market_id, fixed_only=True)
        return orders

    def get_floating_markets_tokens_and_prices(self):
        result = self.inf_rest.get_floating_rate_market_details()
        self.floating_markets = Mhf.convert_list_of_dicts_to_dict(result['markets'], 'tokenId')
        self.floating_tokens_and_prices = Mhf.convert_list_of_dicts_to_dict(result['tokens'], 'tokenId')

    def get_floating_rate_market_history(self, floating_market_id):
        result = self.inf_rest.get_floating_rate_market_details_by_market_id(floating_market_id)
        return float(result['market']['price'])  # Inf.get_floating_rate_market_history(floating_market_id, self.domain, self.verify)

    def get_recent_fixed_rate_market_transactions(self, fixed_rate_market_id):
        result = self.inf_rest.get_recent_fixed_rate_transactions_by_market_id(fixed_rate_market_id, 1)
        return float(result['trxs'][0]['price'])  # Inf.get_recent_fixed_rate_market_transactions(fixed_rate_market_id,  self.domain, self.verify)

    def get_floating_rate_orders(self, token_id, wallet_id=None):
        if wallet_id is None:
            wallet_id = self.get_wallet_id()
        market_id = self.get_market_id_etc_from_token_id(token_id, True, 0)
        orders = self.find_active_orders_by_wallet_and_market(market_id, floating_only=True)
        return orders

    def get_last_price(self, token):
        if token is not None:
            last_px = float(self.floating_tokens_and_prices[self.get_token_id_from_floating_tokens(token)]['price'])
            return last_px
        else:
            logging.fatal(f'No last price for {token}')
            os._exit(1)

    def get_market_id_etc_from_token_id(self, token_id, is_floating_market, days_to_maturity=0,
                                        just_return_market_id=True):
        if is_floating_market:
            if just_return_market_id:
                return self.floating_markets[token_id]['marketId']
            else:
                return self.floating_markets[token_id]['marketId'], \
                    self.floating_markets[token_id]['quantityStep'], \
                    self.floating_markets[token_id]['priceStep']
        else:
            for fm in self.fixed_markets[token_id]:
                if fm['daysToMaturity'] == days_to_maturity:
                    if just_return_market_id:
                        return fm['marketId']
                    else:
                        return fm['marketId'], fm['quantityStep'], fm['priceStep']
        logging.error(f'Cannot find token id {token_id} in markets')

    def get_token_from_floating_market(self, token_id):
        code = self.floating_markets[token_id]['code']
        if code[-5:] != '-SPOT':
            raise Exception(f'Error trying to find code in floating market for token id {token_id}')
        return code[0:len(code)-5]

    def get_token_from_floating_market_id(self, floating_market_id):
        token_id = Mhf.get_token_id_from_market_id_and_markets(floating_market_id, self.floating_markets)
        return self.floating_tokens_and_prices[token_id]['code']

    def get_token_id_and_relevant_market_id_etc(self, token, tenor):
        token_id = self.get_token_id_from_floating_tokens(token)
        floating_market_id = self.get_market_id_etc_from_token_id(token_id, True, 0)
        days_to_maturity = Mhf.convert_tenor_to_n_days(tenor)
        if tenor == 'FLOAT':
            this_market_id, quantity_step, price_step = \
                self.get_market_id_etc_from_token_id(token_id, True, 0, False)
        else:
            this_market_id, quantity_step, price_step = \
                self.get_market_id_etc_from_token_id(token_id, False, days_to_maturity, False)
        return token_id, floating_market_id, this_market_id, quantity_step, price_step

    def get_token_id_from_floating_tokens(self, token):
        for token_id in self.floating_tokens_and_prices:
            if self.floating_tokens_and_prices[token_id]['code'] == token:
                return token_id
        logging.error(f'Cannot find token {token} in floating tokens {self.floating_tokens_and_prices}')

    def get_trading_wallet_details(self, wallet_name='Trading'):
        for wallet in self.wallets:
            if wallet['name'] == wallet_name:
                return wallet
        logging.fatal(f'Cannot find wallet called {wallet_name}')
        os._exit(1)

    def get_wallet_id(self, wallet_name='Trading'):
        for wallet in self.wallets:
            if wallet['name'] == wallet_name:
                return wallet['walletId']
        logging.fatal(f'Cannot find wallet called {wallet_name}')
        os._exit(1)

    def list_all_fixed_rate_markets(self):
        # logging.info('Getting fixed rate markets... please wait')
        fixed_rate_markets = {}
        for token_id in self.floating_tokens_and_prices:
            fixed_rate_markets[token_id] = self.inf_rest.get_active_fixed_rate_markets_by_token_id(token_id)['markets']  # Inf.list_fixed_rate_markets(self.domain, token_id, self.verify)
        # logging.info('Getting fixed rate markets... DONE')
        self.fixed_markets = fixed_rate_markets
        all_fixed_rate_market_dates_look_ok = self.check_if_all_fixed_rate_market_dates_look_ok()
        if all_fixed_rate_market_dates_look_ok:
            self.fixed_markets_last_updated = dt.datetime.now(dt.timezone.utc)
        else:
            os._exit(1)

    def process_orders(self, borrow_order_positions_by_token, lend_order_positions_by_token, active_orders):
        for active_order in active_orders:
            if 'code' in active_order:
                code = active_order['code']
            else:
                code = self.get_token_from_floating_market_id(active_order['marketId'])
            match active_order['side']:
                case Osi.BORROW:
                    if active_order['marketId'] not in borrow_order_positions_by_token:
                        borrow_order_positions_by_token[code] = 0
                    borrow_order_positions_by_token[code] = \
                        borrow_order_positions_by_token[code] + float(active_order['quantity'])
                case Osi.LEND:
                    if active_order['marketId'] not in lend_order_positions_by_token:
                        lend_order_positions_by_token[code] = 0
                    lend_order_positions_by_token[code] = \
                        lend_order_positions_by_token[code] + float(active_order['quantity'])
                case _:
                    logging.fatal(f"Unrecognized side ({active_order['side']})"
                                    + "for active order {active_order['orderId']}.")
                    os._exit(1)
        return borrow_order_positions_by_token, lend_order_positions_by_token

    def run_loop(self):
        while True:  # Loop
            if self.fixed_markets_last_updated is None:
                os._exit(1)
            if self.fixed_markets_last_updated < last_rollover_datetime():
                os._exit(1)
            # if not Inf.infinity_servers_are_ok(self.domain, self.verify):
            #     os._exit(1)
            if self.ok_to_update_active_orders:
                self.update_active_orders()
            self.update_last_prices()
            self.update_bid_ask_last_rates()
            self.wallet_details = self.inf_rest.get_user_wallet_details()['wallet']  # Inf.list_wallet_details(self.get_wallet_id(), self.domain, self.cookies, self.verify)
            sleep(self.cfg['inf_api_bot_refresh_minutes'] * 60)

    def send_order(
            self, market_id, is_floating_market, order_type, side, qty, price, qty_step, price_step, log_prefix=''):
        if self.send_orders:
            deduplication = uuid.uuid4().hex[:8]
            if is_floating_market:
                self.inf_rest.create_floating_rate_order(market_id, order_type, side, qty, price, deduplication)
            else:
                self.inf_rest.create_fixed_rate_order(market_id, order_type, side, qty, price, deduplication)
            # Inf.send_order(
            #    self.get_wallet_id(), market_id, is_floating_market, order_type, side, qty, price, qty_step, price_step,
            #    self.user_agent, self.domain, self.cookies, self.verify, log_prefix)

    def start_bot(self):
        Thread(target=self.run_loop, daemon=True).start()

    def update_active_orders(self):
        # result_floating = self.inf_rest.get_users_floating_rate_orders()
        # result_fixed = self.inf_rest.get_users_fixed_rate_orders()
        self.active_floating_orders, self.active_fixed_orders =\
            Inf.fetch_all_floating_and_fixed_active_orders_by_wallet(
                self.get_wallet_id(), 999999, self.domain, self.cookies, self.verify)
        pass

    def update_bid_ask_last_rates(self):
        min_bid_n_ask_size = 0
        for token_id in self.floating_markets:
            try:
                self.bid_ask_last_rates[token_id] = self.inf_rest.get_current_best_bid_ask_by_token_id(token_id, None, min_bid_n_ask_size)
                # response = Inf.fetch_bid_ask_last_rates(token_id, self.domain, min_bid_n_ask_size, self.verify)
                # self.bid_ask_last_rates[token_id] = response.json()['data']
            except Exception as e:
                logging.fatal(f'Error {e} - Cannot save bid ask last rate data in self.bid_ask_last_rates')
                os._exit(1)

    def update_last_prices(self):
        self.floating_tokens_and_prices = Mhf.convert_list_of_dicts_to_dict(self.inf_rest.get_token_details()['tokens'], 'tokenId')  # Inf.list_tokens(self.domain, self.verify)
        pass
