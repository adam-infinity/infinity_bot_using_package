from constants import OrderSide as Osi
from constants import OrderType as Ot
from constants import RateOffsetRef as Ror
import logging
from misc import MiscHelperFunctions as Mhf
from time import sleep


class TokenBot:

    def __init__(self, bot_name, api_bot, token, tenor, order_type, start_delay, bot_speed, order_size_usd,
                 rate_offset_ref, rate_offset_bps, max_borrow_usd_for_account, max_lend_usd_for_account,
                 max_borrow_usd_for_token, max_lend_usd_for_token, order_book_min_usd, order_book_max_usd,
                 max_limit_orders_per_side, start_bot=True):

        self.bot_name = bot_name
        self.api_bot = api_bot
        self.token = token
        self.tenor = tenor
        self.is_floating_market = False
        if self.tenor == 'FLOAT':
            self.is_floating_market = True
        self.orderType = order_type
        self.startDelayMinute = start_delay
        self.botSpeed = bot_speed
        self.orderSizeUSD = order_size_usd
        self.rateOffsetRef = rate_offset_ref
        self.rateOffsetBPS = rate_offset_bps
        self.maxBorrowUSDForAccount = max_borrow_usd_for_account
        self.maxLendUSDForAccount = max_lend_usd_for_account
        self.maxBorrowUSDForToken = max_borrow_usd_for_token
        self.maxLendUSDForToken = max_lend_usd_for_token
        self.orderBookMinUSD = order_book_min_usd
        self.orderBookMaxUSD = order_book_max_usd
        self.maxLimitOrdersPerSide = max_limit_orders_per_side
        self.wallet_id = self.api_bot.get_wallet_id()
        self.token_id, self.floating_market_id, self.this_market_id, self.quantityStep, self.priceStep =\
            self.api_bot.get_token_id_and_relevant_market_id_etc(token, self.tenor)

        if start_bot:
            self.start_bot()

    def __str__(self):
        return_str = f'token:\t\t{self.token}\n'\
                     + f'orderType:\t{self.orderType}\n' \
                     + f'startDelayMinute:\t\t{self.startDelayMinute}\n' \
                     + f'orderSizeUSD:\t\t\t{self.orderSizeUSD}\n' \
                     + f'rateOffsetRef:\t\t\t{self.rateOffsetRef}\n' \
                     + f'rateOffsetBPS:\t\t\t{self.rateOffsetBPS}\n' \
                     + f'maxBorrowUSDForAccount:\t\t\t{self.maxBorrowUSDForAccount}\n' \
                     + f'maxLendUSDForAccount:\t\t\t{self.maxLendUSDForAccount}\n' \
                     + f'maxBorrowUSDForToken:\t\t\t{self.maxBorrowUSDForToken}\n' \
                     + f'maxLendUSDForToken:\t\t\t{self.maxLendUSDForToken}\n' \
                     + f'orderBookMinUSD:\t\t\t{self.orderBookMinUSD}\n' \
                     + f'orderBookMaxUSD:\t\t\t{self.orderBookMaxUSD}\n'
        return return_str

    def cancel_all_orders(self):
        logging.info('Cancelling all orders...')
        self.api_bot.cancel_all_orders(self.wallet_id, self.market_id)

    def cancel_current_floating_orders(self):
        orders = self.api_bot.get_floating_rate_orders(self.token_id, self.wallet_id)
        bid_orders, ask_orders = Mhf.separate_bid_n_ask_orders(orders)
        days_to_maturity = Mhf.convert_tenor_to_n_days(self.tenor)
        if days_to_maturity != 0:
            raise Exception(f'self.days_to_maturity ({days_to_maturity}) != 0')

        # CANCEL ORDERS IF REACHED MAX NUMBER ORDERS IN ORDER BOOK
        if len(bid_orders) > self.maxLimitOrdersPerSide:
            for i in range(0, len(bid_orders) - self.maxLimitOrdersPerSide):
                self.api_bot.cancel_floating_order(bid_orders[i]['orderId'])
        if len(ask_orders) > self.maxLimitOrdersPerSide:
            for i in range(0, len(ask_orders) - self.maxLimitOrdersPerSide):
                self.api_bot.cancel_floating_order(ask_orders[i]['orderId'])

    def cancel_current_fixed_orders(self):
        days_to_maturity = Mhf.convert_tenor_to_n_days(self.tenor)
        orders = self.api_bot.get_fixed_rate_orders(self.token_id, days_to_maturity)
        bid_orders, ask_orders = Mhf.separate_bid_n_ask_orders(orders)

        # CANCEL ORDERS IF REACHED MAX NUMBER ORDERS IN ORDER BOOK
        if len(bid_orders) > self.maxLimitOrdersPerSide:
            for i in range(0, len(bid_orders) - self.maxLimitOrdersPerSide):
                self.api_bot.cancel_fixed_order(bid_orders[i]['orderId'])
        if len(ask_orders) > self.maxLimitOrdersPerSide:
            for i in range(0, len(ask_orders) - self.maxLimitOrdersPerSide):
                self.api_bot.cancel_fixed_order(ask_orders[i]['orderId'])

    def cancel_current_orders(self):
        logging.info(
            'Preparing cancel current orders for: '
            + f'{self.bot_name}\t'
            + f'{self.token}\t'
            + f'{self.tenor}\t'
            + f'qty: {self.orderSizeUSD}\t'
            + f'rate: {self.rateOffsetBPS}')
        if self.tenor == 'FLOAT':
            self.cancel_current_floating_orders()
        else:  # FIXED
            self.cancel_current_fixed_orders()

    def send_new_floating_orders(self):
        days_to_maturity = Mhf.convert_tenor_to_n_days(self.tenor)
        orders = self.api_bot.get_floating_rate_orders(self.token_id, self.wallet_id)
        bid_orders, ask_orders = Mhf.separate_bid_n_ask_orders(orders)
        bid, ask = self.api_bot.get_best_bid_ask(self.token, True, days_to_maturity, 0)
        # TODO - UN-FALSE THE FOLLOWING
        if False:  # bid > 0 and ask > 0:
            mid = (bid + ask) / 2
        else:
            mid = self.api_bot.get_floating_rate_market_history(self.floating_market_id)
        last_price = self.api_bot.get_last_price(self.token)
        total_bid_orders_in_usd = Mhf.get_total_orders_in_usd(bid_orders, last_price)
        total_ask_orders_in_usd = Mhf.get_total_orders_in_usd(ask_orders, last_price)

        match self.rateOffsetRef.lower():
            case Ror.BBA:
                if bid > 0:
                    ref = bid
                else:
                    if mid > 0:
                        ref = mid
                    else:
                        raise Exception('Non-positive bid & mid')
            case Ror.MID:
                if mid > 0:
                    ref = mid
                else:
                    raise Exception('Non-positive mid')
            case _:
                raise Exception('Unrecognized value for rateOffsetRef')
        if str(self.orderType).strip().upper() == 'MARKET':
            new_buy_order_type = Ot.MARKET_NUM
            new_buy_order_rate_level = ref
        else:  # LIMIT
            new_buy_order_type = Ot.LIMIT_NUM
            new_buy_order_rate_level = ref - ref * self.rateOffsetBPS / 10000

        match self.rateOffsetRef.lower():
            case Ror.BBA:
                if ask > 0:
                    ref = ask
                else:
                    if mid > 0:
                        ref = mid
                    else:
                        raise Exception('Non-positive ask & mid')
            case Ror.MID:
                if mid > 0:
                    ref = mid
                else:
                    raise Exception('Non-positive mid')
            case _:
                raise Exception('Unrecognized value for rateOffsetRef')

        if self.orderType.strip().upper() == 'MARKET':
            new_sell_order_type = Ot.MARKET_NUM
            new_sell_order_rate_level = ref
        else:
            new_sell_order_type = Ot.LIMIT_NUM
            new_sell_order_rate_level = ref + ref * self.rateOffsetBPS / 10000

        new_buy_order_usd = self.orderSizeUSD
        new_sell_order_usd = self.orderSizeUSD

        # For each side:
        #   If is_limit_order AND current orderbook + order qty > maxQty (for token) then don't place order.
        #   If current position + current orderbook position + order qty > maxForToken then don't place order.
        #   If current positions + all current orderbook positions + order qty > maxForAccount then don't place order.
        #   Otherwise, place order.

        token_total_borrow_usd, token_total_lend_usd, wallet_total_borrow_usd, wallet_total_lend_usd = \
            self.api_bot.get_current_positions_and_orders_in_usd(self.token_id)

        if new_buy_order_type == Ot.MARKET_NUM or \
                (new_buy_order_type == Ot.LIMIT_NUM and
                 total_bid_orders_in_usd + new_buy_order_usd < self.orderBookMaxUSD):
            if token_total_borrow_usd + new_buy_order_usd < self.maxBorrowUSDForToken:
                if wallet_total_borrow_usd + new_buy_order_usd < self.maxBorrowUSDForAccount:
                    new_buy_order_qty = new_buy_order_usd / last_price
                    self.api_bot.send_order(
                        self.this_market_id, self.is_floating_market, new_buy_order_type, Osi.BORROW_NUM,
                        new_buy_order_qty, new_buy_order_rate_level, self.quantityStep, self.priceStep,
                        self.token + ' : ' + str(days_to_maturity))

        if new_sell_order_type == Ot.MARKET_NUM or \
                (new_sell_order_type == Ot.LIMIT_NUM and
                 total_ask_orders_in_usd + new_sell_order_usd < self.orderBookMaxUSD):
            if token_total_lend_usd + new_sell_order_usd < self.maxLendUSDForToken:
                if wallet_total_lend_usd + new_sell_order_usd < self.maxLendUSDForAccount:
                    new_sell_order_qty = new_sell_order_usd / last_price
                    self.api_bot.send_order(
                        self.this_market_id, self.is_floating_market, new_sell_order_type, Osi.LEND_NUM,
                        new_sell_order_qty, new_sell_order_rate_level, self.quantityStep, self.priceStep,
                        self.token + ' : ' + str(days_to_maturity))

    def send_new_fixed_orders(self):
        days_to_maturity = Mhf.convert_tenor_to_n_days(self.tenor)
        orders = self.api_bot.get_fixed_rate_orders(self.token_id, days_to_maturity)
        bid_orders, ask_orders = Mhf.separate_bid_n_ask_orders(orders)
        bid, ask = self.api_bot.get_best_bid_ask(self.token, False, days_to_maturity, 0)
        # TODO UN-FALSE THE FOLLOWING:
        if False:  # bid > 0 and ask > 0:
            mid = (bid + ask) / 2
        else:
            mid = self.api_bot.get_recent_fixed_rate_market_transactions(self.this_market_id)
            if mid is not None:
                pass
            elif mid is None and bid > 0:
                mid = bid
            elif mid is None and ask > 0:
                mid = ask
            else:
                mid = self.api_bot.get_linearly_interpolated_rate(
                    self.token, self.token_id, self.this_market_id, self.floating_market_id)

        last_price = self.api_bot.get_last_price(self.token)
        total_bid_orders_in_usd = Mhf.get_total_orders_in_usd(bid_orders, last_price)
        total_ask_orders_in_usd = Mhf.get_total_orders_in_usd(ask_orders, last_price)

        match self.rateOffsetRef.lower():
            case Ror.BBA:
                if bid > 0:
                    ref = bid
                else:
                    if mid > 0:
                        ref = mid
                    else:
                        raise Exception('Non-positive bid & mid')
            case Ror.MID:
                if mid > 0:
                    ref = mid
                else:
                    raise Exception('Non-positive mid')
            case _:
                raise Exception('Unrecognized value for rateOffsetRef')

        if self.orderType.strip().upper() == 'MARKET':
            new_buy_order_type = Ot.MARKET_NUM
            new_buy_order_rate_level = ref  # Shouldn't matter what this value is
        else:
            new_buy_order_type = Ot.LIMIT_NUM
            new_buy_order_rate_level = ref - ref * self.rateOffsetBPS / 10000

        match self.rateOffsetRef.lower():
            case Ror.BBA:
                if ask > 0:
                    ref = ask
                else:
                    if mid > 0:
                        ref = mid
                    else:
                        raise Exception('Non-positive ask & mid')
            case Ror.MID:
                if mid > 0:
                    ref = mid
                else:
                    raise Exception('Non-positive mid')
            case _:
                raise Exception('Unrecognized value for rateOffsetRef')

        if self.orderType.strip().upper() == 'MARKET':
            new_sell_order_type = Ot.MARKET_NUM
            new_sell_order_rate_level = ref
        else:
            new_sell_order_type = Ot.LIMIT_NUM
            new_sell_order_rate_level = ref + ref * self.rateOffsetBPS / 10000

        new_buy_order_usd = self.orderSizeUSD
        new_sell_order_usd = self.orderSizeUSD

        # For each side:
        #   If is_limit_order AND current orderbook + order qty > maxQty (for token) then don't place order.
        #   If current position + current orderbook position + order qty > maxForToken then don't place order.
        #   If current positions + all current orderbook positions + order qty > maxForAccount then don't place order.
        #   Otherwise, place order.

        token_total_borrow_usd, token_total_lend_usd, wallet_total_borrow_usd, wallet_total_lend_usd = \
            self.api_bot.get_current_positions_and_orders_in_usd(self.token_id)

        if new_buy_order_type == Ot.MARKET_NUM or \
            (new_buy_order_type == Ot.LIMIT_NUM and
                total_bid_orders_in_usd + new_buy_order_usd < self.orderBookMaxUSD):
            if token_total_borrow_usd + new_buy_order_usd < self.maxBorrowUSDForToken:
                if wallet_total_borrow_usd + new_buy_order_usd < self.maxBorrowUSDForAccount:
                    new_buy_order_qty = new_buy_order_usd / last_price
                    self.api_bot.send_order(
                        self.this_market_id, self.is_floating_market, new_buy_order_type, Osi.BORROW_NUM,
                        new_buy_order_qty, new_buy_order_rate_level, self.quantityStep, self.priceStep,
                        self.token + ' : ' + str(days_to_maturity))
                else:
                    logging.warning(f'maxBorrowUSDForAccount for breached\t\tDetails:\tmaxBorrowUSDForAccount '
                                    + f'({self.maxBorrowUSDForAccount}) < wallet_total_borrow_usd '
                                    + f'({wallet_total_borrow_usd}) + new_buy_order_usd ({new_buy_order_usd})')
            else:
                logging.warning(f'maxBorrowUSDForToken for breached\t\tDetails:\tmaxBorrowUSDForToken '
                                + f'({self.maxBorrowUSDForToken}) < token_total_borrow_usd '
                                + f'({token_total_borrow_usd}) + new_buy_order_usd ({new_buy_order_usd})')
        else:
            logging.warning(f'orderBookMaxUSD for breached\t\tDetails:\torderBookMaxUSD '
                            + f'({self.orderBookMaxUSD}) < total_bid_orders_in_usd '
                            + f'({total_bid_orders_in_usd}) + new_buy_order_usd ({new_buy_order_usd})')

        if new_sell_order_type == Ot.MARKET_NUM or \
                (new_sell_order_type == Ot.LIMIT_NUM and
                 total_ask_orders_in_usd + new_sell_order_usd < self.orderBookMaxUSD):
            if token_total_lend_usd + new_sell_order_usd < self.maxLendUSDForToken:
                if wallet_total_lend_usd + new_sell_order_usd < self.maxLendUSDForAccount:
                    new_sell_order_qty = new_sell_order_usd / last_price
                    self.api_bot.send_order(
                        self.this_market_id, self.is_floating_market, new_sell_order_type, Osi.LEND_NUM,
                        new_sell_order_qty, new_sell_order_rate_level, self.quantityStep, self.priceStep,
                        self.token + ' : ' + str(days_to_maturity))
                else:
                    logging.warning(f'maxLendUSDForAccount for breached\t\tDetails:\tmaxLendUSDForAccount '
                                    + f'({self.maxLendUSDForAccount}) < wallet_total_lend_usd '
                                    + f'({wallet_total_lend_usd}) + new_sell_order_usd ({new_sell_order_usd})')
            else:
                logging.warning(f'maxLendUSDForToken for breached\t\tDetails:\tmaxLendUSDForToken '
                                + f'({self.maxLendUSDForToken}) < token_total_lend_usd '
                                + f'({token_total_lend_usd}) + new_sell_order_usd ({new_sell_order_usd})')
        else:
            logging.warning(f'orderBookMaxUSD for breached\t\tDetails:\torderBookMaxUSD '
                            + f'({self.orderBookMaxUSD}) < total_ask_orders_in_usd '
                            + f'({total_ask_orders_in_usd}) + new_sell_order_usd ({new_sell_order_usd})')

    def send_new_orders(self):
        logging.info(
            'Preparing new send orders for: '
            + f'{self.bot_name}\t'
            + f'{self.token}\t'
            + f'{self.tenor}\t'
            + f'qty: {self.orderSizeUSD}\t'
            + f'rate: {self.rateOffsetBPS}')
        if self.tenor == 'FLOAT':
            self.send_new_floating_orders()
        else:  # FIXED
            self.send_new_fixed_orders()

    def start_bot(self):
        sleep(self.startDelayMinute)  # Delay start
        while True:  # Loop
            self.cancel_current_orders()
            self.send_new_orders()
            sleep(1.0 / float(self.botSpeed))
