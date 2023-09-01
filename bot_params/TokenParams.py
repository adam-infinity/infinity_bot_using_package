from constants import OrderType as Ot


class TokenParams:

    def __init__(self, token):
        self.token = token
        self.orderType = None
        self.rateOffsetRef = None
        self.startDelayMinute = None
        self.botSpeed = None
        self.orderSizeUSD = None
        self.rateOffsetBPS = None
        self.orderBookMinUSD = None
        self.orderBookMaxUSD = None
        self.maxBorrowUSDForToken = None
        self.maxLendUSDForToken = None
        self.maxLimitOrdersPerSide = None
        self.tenors = None

    def __str__(self):
        return self.get_string()

    def get_string(self):
        return f'token:\t\t{self.token}\n'\
            + f'orderType:\t{self.orderType}\n' \
            + f'rateOffsetRef:\t{self.rateOffsetRef}\n' \
            + f'startDelayMinute:\t\t{self.startDelayMinute}\n' \
            + f'orderSizeUSD:\t\t\t{self.orderSizeUSD}\n' \
            + f'rateOffsetBPS:\t\t\t{self.rateOffsetBPS}\n' \
            + f'orderBookMinUSD:\t\t\t{self.orderBookMinUSD}\n' \
            + f'orderBookMaxUSD:\t\t\t{self.orderBookMaxUSD}\n' \
            + f'maxBorrowUSDForToken:\t\t\t{self.maxBorrowUSDForToken}\n' \
            + f'maxLendUSDForToken:\t\t\t{self.maxLendUSDForToken}\n' \
            + f'tenors:\t\t\t{self.tenors}\n'

    def set_from_all_params(self, all_params):
        # If exists in all_params, populate each param one at a time
        if 'orderType' in all_params:
            self.orderType = all_params['orderType']
        if 'rateOffsetRef' in all_params:
            self.rateOffsetRef = all_params['rateOffsetRef']
        if 'startDelayMinute' in all_params:
            self.startDelayMinute = all_params['startDelayMinute']
        if 'botSpeed' in all_params:
            self.botSpeed = all_params['botSpeed']
        if 'orderSizeUSD' in all_params:
            self.orderSizeUSD = all_params['orderSizeUSD']
        if 'rateOffsetBPS' in all_params:
            self.rateOffsetBPS = all_params['rateOffsetBPS']
        if 'orderBookMinUSD' in all_params:
            self.orderBookMinUSD = all_params['orderBookMinUSD']
        if 'orderBookMaxUSD' in all_params:
            self.orderBookMaxUSD = all_params['orderBookMaxUSD']
        if 'maxBorrowUSDForToken' in all_params:
            self.maxBorrowUSDForToken = all_params['maxBorrowUSDForToken']
        if 'maxLendUSDForToken' in all_params:
            self.maxLendUSDForToken = all_params['maxLendUSDForToken']
        if 'maxLimitOrdersPerSide' in all_params:
            self.maxLimitOrdersPerSide = all_params['maxLimitOrdersPerSide']
        if 'tenors' in all_params:
            self.tenors = all_params['tenors']

    def add_from_this_token_params(self, this_token_params):
        # If exists in this_token_params, populate/overwrite each param one at a time
        if 'orderType' in this_token_params:
            self.orderType = this_token_params['orderType']
        if 'rateOffsetRef' in this_token_params:
            self.rateOffsetRef = this_token_params['rateOffsetRef']
        if 'startDelayMinute' in this_token_params:
            self.startDelayMinute = this_token_params['startDelayMinute']
        if 'botSpeed' in this_token_params:
            self.botSpeed = this_token_params['botSpeed']
        if 'orderSizeUSD' in this_token_params:
            self.orderSizeUSD = this_token_params['orderSizeUSD']
        if 'rateOffsetBPS' in this_token_params:
            self.rateOffsetBPS = this_token_params['rateOffsetBPS']
        if 'orderBookMinUSD' in this_token_params:
            self.orderBookMinUSD = this_token_params['orderBookMinUSD']
        if 'orderBookMaxUSD' in this_token_params:
            self.orderBookMaxUSD = this_token_params['orderBookMaxUSD']
        if 'maxBorrowUSDForToken' in this_token_params:
            self.maxBorrowUSDForToken = this_token_params['maxBorrowUSDForToken']
        if 'maxLendUSDForToken' in this_token_params:
            self.maxLendUSDForToken = this_token_params['maxLendUSDForToken']
        if 'maxLimitOrdersPerSide' in this_token_params:
            self.maxLimitOrdersPerSide = this_token_params['maxLimitOrdersPerSide']
        if 'tenors' in this_token_params:
            self.tenors = this_token_params['tenors']
        # Then check that nothing is missing
        self.check_if_any_missing_params()

    def check_if_any_missing_params(self):
        if self.token is None:
            raise Exception('Token not set')
        if self.orderType is None:
            raise Exception('No order type for token ' + self.token)
        if self.rateOffsetRef is None:
            raise Exception('No reference specified for rate offset for token ' + self.token)
        if self.orderType != Ot.LIMIT_STR and self.orderType != Ot.MARKET_STR:
            raise Exception(f'Unrecognized order type ({self.orderType}) for token {self.token}')
        if self.startDelayMinute is None:
            raise Exception('No start delay for token ' + self.token)
        if self.botSpeed is None:
            raise Exception('No bot speed for token ' + self.token)
        if self.botSpeed == 0:  # if self.botSpeed.val == 0:
            raise Exception('Zero bot speed for token ' + self.token)
        if self.orderSizeUSD is None:
            raise Exception('No order size for token ' + self.token)
        if self.rateOffsetBPS is None:
            raise Exception('No rate offset for token ' + self.token)
        if self.orderBookMinUSD is None:
            raise Exception('No USD min order book for token ' + self.token)
        if self.orderBookMaxUSD is None:
            raise Exception('No USD max order book for token ' + self.token)
        if self.maxBorrowUSDForToken is None:
            raise Exception('No USD max borrow for token ' + self.token)
        if self.maxLendUSDForToken is None:
            raise Exception('No USD max lend for token ' + self.token)
        if self.maxLimitOrdersPerSide is None:
            raise Exception('No max limit orders per side for token ' + self.token)
        if self.tenors is None:
            raise Exception('No tenor specified for token ' + self.token)
