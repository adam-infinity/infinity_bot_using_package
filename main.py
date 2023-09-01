from bots import InfinityApiBot as Inf
from bots import ParentBot as Bot
import logging
from other import MiscHelperFunctions as Mhf


if __name__ == '__main__':

    cfg = Mhf.load_config_file_etc()
    verify = bool(cfg['verify'])
    send_orders = bool(cfg['send_orders'])
    cancel_orders = bool(cfg['cancel_orders'])

    Mhf.set_up_logging()

    logging.info('NOTE: To handle \"cannot import name \'getargspec\' from \'inspect\'\" error, '
                 + 'replace \'from inspect import getargspec\' with \'from inspect import getfullargspec\' '
                 + 'in expressions.py file')

    if not send_orders:
        logging.warning('*** SENDING ORDERS CURRENTLY DISABLED. PLS RE-ENABLE. ***')
    if not cancel_orders:
        logging.warning('*** CANCELLING ORDERS CURRENTLY DISABLED. PLS RE-ENABLE. ***')

    api_bot = Inf.InfinityApiBot(verify, send_orders, cancel_orders)
    api_bot.start_bot()

    bots = []  # For storing bots on own threads
    enabled_bot_names = Mhf.get_list_of_enabled_bots()   # Trading bots
    for bot_name in enabled_bot_names:
        bots.append(Bot.ParentBot(bot_name, api_bot, False))

    for bot in bots:
        pass
        bot.start_bot()

    for bot in bots:
        pass
        bot.wait_for_bot_to_stop()
