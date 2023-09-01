from constants import OrderSide as Osi
from constants import RollOverTime as Rot
from contextlib import suppress
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import dotenv
import logging
import yaml


CFG_PATH_FILENAME = 'misc/config.yml'


def add_n_months(this_date, n_months):
    new_year = this_date.year + (this_date.month + n_months - 1) // 12
    new_month = ((this_date.month + n_months - 1) % 12) + 1
    first_date_of_new_date = date(new_year, new_month, 1)
    last_date_of_new_date = get_first_date_of_month(
        get_last_friday_of_month(first_date_of_new_date) + timedelta(days=7)) - timedelta(days=1)
    n_days_in_new_month = last_date_of_new_date.day
    new_day = min(this_date.day, n_days_in_new_month)
    return date(new_year, new_month, new_day)


def add_n_years(this_date, n_years):
    new_year = this_date.year + n_years
    first_date_of_new_date = date(new_year, this_date.month, 1)
    last_date_of_new_date = get_first_date_of_month(
        get_last_friday_of_month(first_date_of_new_date) + timedelta(days=7)) - timedelta(days=1)
    n_days_in_new_month = last_date_of_new_date.day
    new_day = min(this_date.day, n_days_in_new_month)
    return date(new_year, this_date.month, new_day)


def check_is_before_rollover_time(curr_utc_datetime):
    return curr_utc_datetime.time() < time(Rot.HOUR, Rot.MINUTE, Rot.SECOND)


def convert_list_of_dicts_to_dict(list_of_dicts, key_name):
    new_dict = {}
    for this_dict in list_of_dicts:
        new_dict[this_dict[key_name]] = this_dict
    return new_dict


def convert_tenor_to_date(tenor, curr_utc_date_and_time):
    tenor = tenor.upper()
    benchmark_date = curr_utc_date_and_time.date()

    if tenor == 'FLOAT':
        return benchmark_date

    if not tenor[0:-1].isnumeric():
        raise Exception(f'Tenor {tenor} is wrong format. Left character should be number.')

    n = int(tenor[0:-1])

    if check_is_before_rollover_time(curr_utc_date_and_time):
        benchmark_date = benchmark_date - timedelta(days=1)

    match tenor[-1]:
        case 'D':
            return benchmark_date + timedelta(days=n)
        case 'W':
            closest_friday = get_closest_friday(benchmark_date)
            return closest_friday + timedelta(days=7*(n-1))
        case 'M':
            last_friday_of_month = get_last_friday_of_month(benchmark_date)
            first_day_of_month = get_first_date_of_month(benchmark_date)
            if benchmark_date > last_friday_of_month:
                month_offset = 1
            else:
                month_offset = 0
            return get_last_friday_of_month(add_n_months(first_day_of_month, month_offset + n-1))
        case 'Q':
            if benchmark_date.month == 12:
                year_offset = 1
            else:
                year_offset = 0
            if benchmark_date.month < 4:
                target_month_idx = 3
            elif benchmark_date.month < 7:
                target_month_idx = 6
            elif benchmark_date.month < 10:
                target_month_idx = 9
            else:
                target_month_idx = 12
            t1 = add_n_years(benchmark_date, year_offset)
            t1 = date(t1.year, target_month_idx, t1.day)
            return get_last_friday_of_month(add_n_months(get_last_friday_of_month(t1), 3*(n-1)))
        case _:
            raise Exception(f'Date code {tenor} is wrong format. Right character should be D, W, M, Q only.')


def convert_tenor_to_n_days(tenor):
    if tenor == 'FLOAT':
        return 0
    curr_utc_date_and_time = datetime.now(timezone.utc)
    tenor_date = convert_tenor_to_date(tenor, curr_utc_date_and_time)
    n_days_to_maturity = tenor_date - curr_utc_date_and_time.date()
    n_days_to_maturity = n_days_to_maturity.days
    if check_is_before_rollover_time(curr_utc_date_and_time):
        n_days_to_maturity = n_days_to_maturity + 1
    if n_days_to_maturity < 0:
        raise Exception(f'Tenor {tenor} is giving negative days to maturity.')
    return n_days_to_maturity


def get_closest_friday(this_date):
    while this_date.weekday() != 4:
        this_date = this_date + timedelta(days=1)
    return this_date


def get_first_date_of_month(this_date):
    return datetime(this_date.year, this_date.month, 1).date()


def get_last_friday_of_month(this_date):
    last_day = 31
    last_date_found = False
    while not last_date_found:
        with suppress(Exception):
            last_friday_of_month = datetime(this_date.year, this_date.month, last_day).date()
            last_date_found = True
        last_day = last_day - 1
    while last_friday_of_month.weekday() != 4:  # 4 = Friday
        last_friday_of_month = last_friday_of_month - timedelta(days=1)
    return last_friday_of_month


def get_list_of_enabled_bots():
    with open(CFG_PATH_FILENAME, 'r') as ymlFile:
        cfg = yaml.safe_load(ymlFile)
    enabled_bot_names = []
    for item in cfg:
        try:
            if item[0:4] == 'bot_':
                if cfg[item]['enable'] == 1:
                    enabled_bot_names.append(item)
        finally:
            pass
    return enabled_bot_names


def get_logging_level(logging_level):
    match logging_level.upper():
        case 'CRIT':
            return logging.CRITICAL
        case 'CRITICAL':
            return logging.CRITICAL
        case 'DEBUG':
            return logging.DEBUG
        case 'ERR':
            return logging.ERROR
        case 'ERROR':
            return logging.ERROR
        case 'FATAL':
            return logging.FATAL
        case 'INFO':
            return logging.INFO
        case 'WARN':
            return logging.WARNING
        case 'WARNING':
            return logging.WARNING
        case _:
            raise Exception(f'Cannot recognize logging level {logging_level}')


def get_token_id_from_market_id_and_markets(market_id, markets):
    for token_id in markets:
        if markets[token_id]['marketId'] == market_id:
            return token_id
    raise Exception(f'Cannot find market id {market_id} in markets {markets}')


def get_total_orders_in_usd(orders, price):
    total_orders = 0.0
    for order in orders:
        total_orders = total_orders + float(order['quantity'])
    return total_orders * price


def load_config_file_etc():
    with open(CFG_PATH_FILENAME, 'r') as ymlFile:
        cfg = yaml.safe_load(ymlFile)
    dotenv.load_dotenv(cfg['env_path_filename'])
    return cfg


def round_value(val, base):
    return Decimal(base) * round(float(val) / float(base))


def roundup_value(val, base):
    return Decimal(base) * round((float(val) + float(base)/2) / float(base))


def separate_bid_n_ask_orders(orders):
    bid_orders = []
    ask_orders = []
    if orders is None:
        return None, None
    for order in orders:
        match order['side']:
            case Osi.BORROW:
                bid_orders.append(order)
            case Osi.LEND:
                ask_orders.append(order)
            case _:
                raise Exception(f"Unrecognized side {order['side']}")
    return bid_orders, ask_orders


def set_up_logging():
    with open(CFG_PATH_FILENAME, 'r') as ymlFile:
        cfg = yaml.safe_load(ymlFile)
    logging.getLogger("urllib3").setLevel(get_logging_level(cfg['logging_level_urllib3']))
    this_format = '%(asctime)s %(levelname)-8s %(message)s'

    if cfg['log_path']:
        t = date.today()
        if cfg['output_logs_to_file']:
            logging.basicConfig(level=get_logging_level(cfg['logging_level']),
                                format=this_format,
                                filename=cfg['log_path'] + 'log_' + t.strftime('%Y%m%d') + '.log',
                                filemode='a')  # 'a' for append. 'w' for overwrite
        else:
            logging.basicConfig(level=get_logging_level(cfg['logging_level']), format=this_format)
        console = logging.StreamHandler()
        console.setLevel(get_logging_level(cfg['logging_level']))
    else:
        logging.basicConfig(level=get_logging_level(cfg['logging_level']), format=this_format)

        console = logging.StreamHandler()
        console.setLevel(get_logging_level(cfg['logging_level']))
        logging.getLogger('urllib3').setLevel(get_logging_level(cfg['logging_level_urllib3']))
