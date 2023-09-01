from bots import TokenBot as Tb
from bot_params import TokenParams as Tp
import copy
import logging
from misc import MiscHelperFunctions as Mhf
from threading import Lock, Thread
from time import sleep


def get_tenors_to_use(tenors, token):
    tenors_to_use = []
    n_days_to_maturity = []
    for tenor in tenors:
        this_n_days_to_maturity = Mhf.convert_tenor_to_n_days(tenor)
        if len(tenors_to_use) == 0 or tenor == '1D':
            tenors_to_use.append(tenor)
            n_days_to_maturity.append(this_n_days_to_maturity)
        else:
            if this_n_days_to_maturity not in n_days_to_maturity:
                tenors_to_use.append(tenor)
                n_days_to_maturity.append(this_n_days_to_maturity)
            else:
                logging.info(f'Duplicate #days to maturity for tenor {tenor}')
    logging.info(f'Number of unique markets for token {token} = {len(tenors_to_use)}')
    return tenors_to_use


class ParentBot:

    def __init__(self, bot_name, api_bot, start_bot=False):

        self.bot_name = bot_name
        self.api_bot = api_bot
        self.token_params_list = None
        self.cfg = Mhf.load_config_file_etc()
        logging.info(f"Domain is {self.cfg['infinity_url']}")
        self.maxBorrowUSDForAccount = None
        self.maxLendUSDForAccount = None
        self.get_account_params()
        self.get_tokens_and_token_params()
        self.threads = self.prepare_threads()  # Prepare threads
        self.lock = Lock()
        if start_bot:
            self.start_bot()

    def __str__(self):
        return_str = '###################################################################\n' +\
                     f'BOT NAME:\t{self.bot_name}\n\n'
        for token_params in self.token_params_list:
            return_str = return_str + str(token_params) + '\n'
        return return_str

    def check_bot_checker(self):
        # Add loop, say every minute, check if all bots are running. If some are not, add those threads. (If possible.)
        sleep(60)
        while True:
            with self.lock:
                i = 0
                current_thread_list_length = len(self.threads)
                while i < current_thread_list_length:
                    t = self.threads[i]
                    if not t.is_alive():
                        if t.name[0:11] == 'botChecker_':
                            del self.threads[i]
                            self.threads.append(Thread(name='botChecker_' + self.bot_name, target=self.check_bots,
                                                       daemon=True))
                            self.threads[-1].start()
                            break
            sleep(60)

    def check_bots(self):
        sleep(60)
        while True:
            with self.lock:
                i = 0
                current_thread_list_length = len(self.threads)
                while i < current_thread_list_length:
                    t = self.threads[i]
                    if t.is_alive():
                        i = i + 1
                    else:  # Delete thread, create new one
                        if t.name[0:18] == 'botCheckerChecker_':
                            del self.threads[i]
                            self.threads.append(
                                Thread(name='botCheckerChecker_' + self.bot_name, target=self.check_bot_checker,
                                       daemon=True))
                            self.threads[-1].start()
                            pass
                        else:
                            current_thread_list_length = current_thread_list_length - 1
                            this_bot_type, bot_name, this_token, tenor = t.name.split('__')
                            logging.warning(f'Restarting thread for {t.name}')
                            for token in self.token_params_list:
                                if token.token == this_token:
                                    del self.threads[i]
                                    self.threads.append(
                                        Thread(name='TB__' + bot_name + '__' + token.token + '__' + tenor,
                                               target=Tb.TokenBot,
                                               args=(bot_name, self.api_bot,
                                                     token.token, tenor,
                                                     token.orderType,
                                                     token.startDelayMinute,
                                                     token.botSpeed,
                                                     token.orderSizeUSD,
                                                     token.rateOffsetRef,
                                                     token.rateOffsetBPS,
                                                     self.maxBorrowUSDForAccount, self.maxLendUSDForAccount,
                                                     token.maxBorrowUSDForToken, token.maxLendUSDForToken,
                                                     token.orderBookMinUSD, token.orderBookMaxUSD,
                                                     token.maxLimitOrdersPerSide,
                                                     self.cfg['token_bot_heartbeat_refresh_minutes']),
                                               daemon=True))
                                    self.threads[-1].start()
            sleep(60)

    def get_account_params(self):
        try:
            self.maxBorrowUSDForAccount = self.cfg[self.bot_name]['maxBorrowUSDForAccount']
            self.maxLendUSDForAccount = self.cfg[self.bot_name]['maxLendUSDForAccount']
        except Exception as e:
            raise Exception(f'Error {e} - Cannot retrieve account parameters')

    def get_tokens(self):
        if self.bot_name in self.cfg:
            tokens = copy.copy(self.cfg[self.bot_name]['tokens'])
            if 'all' in tokens:
                del tokens['all']
            return tokens
        else:
            raise Exception('Bot not found in config file')

    def get_tokens_and_token_params(self):
        self.token_params_list = []
        for token in self.get_tokens():
            token_params = self.get_token_params(token)
            logging.debug(f'bot in params:\t\t{self.bot_name}\n' + str(token_params))
            self.token_params_list.append(token_params)
        pass

    def get_token_params(self, token):
        if self.bot_name in self.cfg:
            token_params = Tp.TokenParams(token)
            tokens = self.cfg[self.bot_name]['tokens']
            if 'all' in tokens:
                if self.cfg[self.bot_name]['tokens']['all'] is not None:
                    all_params = self.cfg[self.bot_name]['tokens']['all']
                    token_params.set_from_all_params(all_params)
            if token in tokens:
                if self.cfg[self.bot_name]['tokens'][token] is not None:
                    this_token_params = self.cfg[self.bot_name]['tokens'][token]
                    # If exists in this_token_params but not yet in token_params, populate each param one at a time
                    token_params.add_from_this_token_params(this_token_params)
        else:
            raise Exception('Bot not found in config file')
        return token_params

    def prepare_threads(self):
        threads = []
        threads.append(Thread(name='botChecker_' + self.bot_name, target=self.check_bots, daemon=True))
        threads.append(Thread(name='botCheckerChecker_' + self.bot_name, target=self.check_bot_checker, daemon=True))
        for token in self.token_params_list:
            tenors_to_use = get_tenors_to_use(token.tenors, token.token)
            for tenor in tenors_to_use:
                threads.append(Thread(name='TB__' + self.bot_name + '__' + token.token + '__' + tenor,
                                      target=Tb.TokenBot,
                                      args=(self.bot_name, self.api_bot,
                                            token.token, tenor,
                                            token.orderType,
                                            token.startDelayMinute,
                                            token.botSpeed,
                                            token.orderSizeUSD,
                                            token.rateOffsetRef,
                                            token.rateOffsetBPS,
                                            self.maxBorrowUSDForAccount, self.maxLendUSDForAccount,
                                            token.maxBorrowUSDForToken, token.maxLendUSDForToken,
                                            token.orderBookMinUSD, token.orderBookMaxUSD,
                                            token.maxLimitOrdersPerSide),
                                      daemon=True))
        return threads

    def start_bot(self):
        for t in self.threads:  # Start threads
            t.start()

    def stop_bot(self):
        logging.info('Stopping child bots for ' + self.bot_name)
        self.stop_bot_event.set()

    def wait_for_bot_to_stop(self):
        for t in self.threads:
            t.join()
