from constants import OrderStatus as Ost
from eth_account.messages import encode_structured_data
import inspect
import logging
import os
from other import MiscHelperFunctions as Mhf
import requests
import time
import uuid
from web3.auto import w3


def cancel_fixed_order(order_id, domain, cookies, verify=False):
    logging.debug(f'{inspect.stack()[0][3]} ({order_id})')
    try:
        response = requests.post(domain + '/api/fixed_rate/order/cancel?orderId=' + str(order_id), cookies=cookies,
                                 verify=verify)
        try:
            if not response.json()['success']:
                logging.debug(str(response.json()))
        except Exception as e:
            logging.warning(f'Exception {e} - Cannot retrieve response as json.  Response is {str(response)}')
    except Exception as e:
        logging.warning(f'Exception {e} - Cannot place order cancellation for fixed orderId {str(order_id)}')


def cancel_floating_order(order_id, domain, cookies, verify=False):
    logging.debug(f'{inspect.stack()[0][3]} ({order_id})')
    res_str = domain + '/api/rate/order/cancel?orderId=' + str(order_id)
    try:
        response = requests.post(res_str, cookies=cookies, verify=verify)
        try:
            if not response.json()['success']:
                logging.debug(str(response.json()))
        except Exception as e:
            logging.warning(f'Exception {e} - Cannot retrieve response as json.  Response is {str(response)}')
    except Exception as e:
        logging.warning(f'Exception {e} - Cannot place order cancellation for floating orderId {str(order_id)}')


def fetch_all_floating_and_fixed_active_orders_by_wallet(wallet_id, max_num_orders, domain, cookies, verify=False):
    # FLOATING
    logging.info('Getting all floating rate orders... please wait')
    active_floating_orders = []
    start_id = 0
    n_orders = 0
    while True:
        res_str = '/api/user/rate/orders?walletId=' + str(wallet_id) + '&limit=' + str(max_num_orders)
        if start_id != 0:
            res_str = res_str + '&startId=' + str(start_id)
        res_str = res_str + '&pending=true'
        response = requests.get(domain + res_str, cookies=cookies, verify=verify)
        orders = []
        try:
            orders = response.json()['data']['orders']
        except Exception as e:
            logging.warning(f'Error {e} - Cannot retrieve orders')
        if len(orders) == 0:
            break
        for order in orders:
            if order['status'] == Ost.STATUS_ON_BOOK:
                active_floating_orders.append(order)
        start_id = orders[-1]['orderId'] - 1
        n_orders = n_orders + len(orders)
        logging.debug(n_orders)
    logging.info('Getting all floating rate orders... DONE')
    logging.debug(f'# Floating orders = {n_orders}')

    # FIXED
    logging.info('Getting all fixed rate orders... please wait')
    active_fixed_orders = []
    start_id = 0
    n_orders = 0
    while True:
        res_str = '/api/user/fixed_rate/orders?walletId=' + str(wallet_id) + '&limit=' + str(max_num_orders)
        if start_id != 0:
            res_str = res_str + '&startId=' + str(start_id)
        res_str = domain + res_str + '&pending=true'
        response = requests.get(res_str, cookies=cookies, verify=verify)
        orders = []
        try:
            orders = response.json()['data']['orders']
        except Exception as e:
            logging.warning(f'Error {e} - Cannot retrieve orders')
        if len(orders) == 0:
            break
        for order in orders:
            if order['status'] == Ost.STATUS_ON_BOOK:
                active_fixed_orders.append(order)
        start_id = orders[-1]['orderId'] - 1
        n_orders = n_orders + len(orders)
        logging.debug(n_orders)
    logging.info('Getting all fixed rate orders... DONE')
    logging.debug(f'# Fixed orders = {n_orders}')

    return active_floating_orders, active_fixed_orders


def fetch_bid_ask_last_rates(token_id, domain, min_bid_n_ask_size=0, verify=False):
    res_str = '/api/p/rate/markets/bestBidNAsk?tokenId=' + str(token_id) + \
              '&min_bid_n_ask_size=' + str(min_bid_n_ask_size)
    response = requests.get(domain + res_str, verify=verify)
    return response


def get_floating_rate_market_history(floating_market_id, domain, verify=False):
    response = requests.get(domain + '/api/p/rate/market/' + str(floating_market_id), verify=verify)
    try:
        return float(response.json()['data']['market']['price'])  # or actualPrice
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve floating rate market {floating_market_id}')
        os._exit(1)


def get_recent_fixed_rate_market_transactions(fixed_rate_market_id, domain, verify=False):
    response = requests.get(domain + '/api/p/fixed_rate/market/' + str(fixed_rate_market_id) + '/trxs/recent?limit=1',
                            verify=verify)
    try:
        if len(response.json()['data']['trxs']) == 0:
            return None
        else:
            return float(response.json()['data']['trxs'][0]['price'])
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve response for whether any trades for fixed rate market ' +
                      f'{fixed_rate_market_id}')
        os._exit(1)


def infinity_servers_are_ok(domain, verify=False):
    res_str = domain + '/api/server/status'
    response = requests.get(res_str, verify=verify)
    try:
        job_server_status = response.json()['data']['jobServerStatus']
        web_server_status = response.json()['data']['webServerStatus']
        trade_server_status = response.json()['data']['tradeServerStatus']
        return job_server_status == 1 and web_server_status == 1 and \
            trade_server_status == 1
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve server status')
        os._exit(1)


def list_fixed_rate_markets(domain, token_id, verify=False):
    res_str = domain + '/api/p/fixed_rate/markets?tokenId=' + str(token_id)
    response = requests.get(res_str, verify=verify)
    try:
        return response.json()['data']['markets']
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve list of fixed rate markets: + {str(response)}')
        os._exit(1)


def list_floating_rate_markets(domain, verify=False):
    response = requests.get(domain + '/api/p/rate/markets?', verify=verify)
    markets = {}
    tokens = {}
    for market in response.json()['data']['markets']:
        markets[market['tokenId']] = market
    for token in response.json()['data']['tokens']:
        tokens[token['tokenId']] = token
    try:
        return markets, tokens
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve list of floating rate markets: + {str(response)}')
        os._exit(1)


def list_tokens(domain, verify=False):
    response = requests.get(domain + '/api/p/tokens', verify=verify)
    try:
        tokens = {}
        for token in response.json()['data']['tokens']:
            tokens[token['tokenId']] = token
        return tokens
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve tokens when trying to list tokens')
        os._exit(1)


def list_wallets(domain, cookies, verify=False):
    response = requests.get(domain + '/api/user/wallets', cookies=cookies, verify=verify)
    try:
        return response.json()['data']['wallets']
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve list of wallets')
        os._exit(1)


def list_wallet_details(wallet_id, domain, cookies, verify=False):
    response = requests.get(domain + '/api/user/wallet/' + str(wallet_id), cookies=cookies, verify=verify)
    try:
        return response.json()['data']['wallet']
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve details for wallet ' + str(wallet_id))
        os._exit(1)


def login(bot_name, address, chain_id, user_agent, domain, cfg, verify=False):
    # Login request
    body = {'addr': address, 'chainId': chain_id}
    logging.debug(body)
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': user_agent}
    i = 0
    while True:
        i = i + 1
        response = requests.post(
            domain + '/api/user/login', data=body, headers=headers, verify=verify)
        if response.status_code != 504:
            break
        logging.warning(f'504 gateway time-out error when trying to log in. Waiting for {min(60 * i, 300)} seconds.')
        time.sleep(min(60 * i, 300))
    try:
        logging.debug(str(response.json()))
    except Exception as e:
        logging.fatal(f'{e} - Cannot retrieve response as json.  Response is {str(response)}')
        os._exit(1)
    if response.status_code != 200:
        logging.fatal(f'Error - Response status code is {response.status_code}')
        os._exit(1)
    try:
        nonce = response.json()['data']['nonceHash']
        eip712_message = response.json()['data']['eip712Message']
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot retrieve response contents')
        os._exit(1)
    # Make signature
    encoded_message = encode_structured_data(text=eip712_message)
    try:
        signed_message = w3.eth.account.sign_message(encoded_message, private_key=os.getenv('PRIVATE_KEY'))
    except Exception as e:
        logging.fatal(f'Error {e} - Cannot sign message. (Missing private key?)')
        os._exit(1)
    body = {'addr': address, 'nonceHash': nonce, 'signature': w3.to_hex(signed_message.signature)}
    logging.debug(body)
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': user_agent}
    response = requests.post(domain + '/api/user/login/verify',
                             data=body, headers=headers, verify=verify)
    try:
        logging.debug(str(response.json()))
    except Exception as e:
        logging.warning(f'Exception {e} - Cannot retrieve response as json.  Response is {str(response)}')
    for c in response.cookies:
        logging.debug(f'{c.name}\t{c.value}')
    return requests.utils.dict_from_cookiejar(response.cookies)


def send_order(wallet_id, market_id, is_floating_market, order_type, side, qty, price, qty_step, price_step, user_agent,
               domain, cookies, verify=False, log_prefix=''):
    if is_floating_market:  # FLOATING
        body = {'marketId': market_id,
                'walletId': wallet_id,
                'side': side,
                'orderType': order_type,
                'quantity': str(Mhf.roundup_value(qty, qty_step)),
                'price': str(Mhf.round_value(price, price_step)),
                'deduplication': uuid.uuid4().hex[:8],  # f'{wallet_id}{market_id}{time.time()}',
                'passive': 0
                }
        headers = {'Content-Type': 'application/json', 'User-Agent': user_agent}
        response = requests.post(domain + '/api/rate/order', json=body, headers=headers, cookies=cookies,
                                 verify=verify)
        try:
            logging.debug(log_prefix + '\t' + str(response.json()))
            pass
        except Exception as e:
            logging.warning(f'Exception {e} - Cannot retrieve response as json.  Response is {str(response)}')

    else:  # FIXED
        body = {'marketId': market_id,
                'walletId': wallet_id,
                'side': side,
                'orderType': order_type,
                'quantity': str(Mhf.roundup_value(qty, qty_step)),
                'price': str(Mhf.round_value(price, price_step)),
                'deduplication': uuid.uuid4().hex[:8],  # f'{wallet_id}{market_id}{time.time()}',
                'passive': 0
                }
        headers = {'Content-Type': 'application/json', 'User-Agent': user_agent}
        response = requests.post(domain + '/api/fixed_rate/order', json=body, headers=headers, cookies=cookies,
                                 verify=verify)
        try:
            logging.debug(log_prefix + '\t' + str(response.json()))
            pass
        except Exception as e:
            logging.warning(f'Exception {e} - Cannot retrieve response as json.  Response is {str(response)}')

    match response.status_code:
        case 200:
            if 'errorMsgKey' in response.json():
                match response.json()['errorMsgKey']:
                    case 'error.market.notExists':
                        logging.fatal(f"For marketId {market_id}: {response.json()['errorMsgKey']}")
                        os._exit(1)
                    case 'error.order.autoCancelled':
                        logging.info(response.json()['errorMsgKey'])
                        pass
                    case 'error.price.negative':
                        logging.info(response.json()['errorMsgKey'])
                        pass
                    case 'error.rateOrder.miniumQuantityNotReach':
                        logging.info(response.json()['errorMsgKey'])
                        pass
                    case 'error.system.timeout':
                        logging.info(response.json()['errorMsgKey'])
                    case _:
                        logging.info(response.json()['errorMsgKey'])
            pass
        case 504:
            logging.info(response)
        case _:
            logging.fatal(f'Error sending order - Response status code is {response.status_code}')
            os._exit(1)

