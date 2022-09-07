#!/usr/bin/env python3
from ib_insync import *
from threading import Thread
from itertools import islice
import time
import random
import asyncio
import datetime
import math
import os
import logging

os.system("")  # enables ansi escape characters in terminal

class BCOLORS:

    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    GRAY = '\033[90m'
    BLACK = '\033[90m'
    ENDC = '\033[0m'


def grouper(n, iterable):

    it = iter(iterable)
    while True:
        chunk = tuple(islice(it, n))
        if not chunk:
            return
        yield chunk


def get_tickers():

    with open('scanner_tickers.csv', encoding="utf-8-sig") as f:
        tickers = [l.strip() for l in f.readlines()]

    return tickers


def get_dte(symbol_with_date, right):

    if right == 'P':
        expiration_day = str(symbol_with_date).split('_')[1].split('P')[0]
    else:
        expiration_day = str(symbol_with_date).split('_')[1].split('C')[0]

    today = datetime.datetime.today()
    date_format = "%m%d%y"

    expiration_day = datetime.datetime.strptime(expiration_day, date_format)
    delta = expiration_day - today
    dte = delta.days + 1  # we add 1 to ensure we don't have off by 1 error on days left

    return dte


def percent_diff(price, strike):

    return int((abs(price - strike) / price) * 100)


def float_is_integer(num):

    if num.is_integer():
        return int(num)

    return num


def process(tlist):

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ib = IB()
    client_id = random.randrange(1, 10000)
    try:
        ib.connect('127.0.0.1', 7496, readonly=True, clientId=client_id)
    except ConnectionRefusedError:
        print('Connection error')
        return

    # real time by default, 2 is frozen market data for testing
    ib.reqMarketDataType(3)

    count = 0
    # qualify and gather tickers in advance
    stocks = []
    stockstore = {}
    for t in tlist:
        stock = Stock(t, exchange='SMART', currency='USD', primaryExchange='ISLAND')
        stocks.append(stock)
        stockstore[t] = {'contract': stock, 'ticker': None}
    ib.qualifyContracts(*stocks)
    tickers = ib.reqTickers(*stocks)

    for tick in tickers:
        stockstore[tick.contract.symbol]['ticker'] = tick

    # test
    order = LimitOrder('SELL', 1.0, 0.05)

    # create contracts for each
    for t in tlist:
        count += 1

        stock = stockstore[t]['contract']
        ticker = stockstore[t]['ticker']
        price = ticker.last
        
        # get the options chains for each ticker
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        chain = next(c for c in chains if c.exchange == 'SMART')
        
        # get the closest expiration's chain
        # filter and create contracts for only those that are at least X% otm
        try:
            strikes = [strike for strike in chain.strikes if percent_diff(price, strike) >= PERCENT_OTM]
        except (ValueError, ZeroDivisionError):
            continue
        expirations = sorted(exp for exp in chain.expirations)[:3]
        rights = ['P', 'C']
        contracts = [
            Option(stock.symbol, expiration, strike, right, 'SMART')
            for right in rights
            for expiration in expirations
            for strike in strikes if right == 'P' and strike < price or right == 'C' and strike > price
        ]
        contracts = ib.qualifyContracts(*contracts)
        
        # get the market data for all of these options contracts
        tickers = ib.reqTickers(*contracts)

        # print contracts if they have a bid size > 0
        for tick in tickers:
            if tick.bidSize > 0:
                symbol_date = datetime.datetime.strptime(tick.contract.lastTradeDateOrContractMonth, '%Y%m%d').\
                    strftime('%m%d%y')
                option_symbol = f"{tick.contract.symbol}_{symbol_date}{tick.contract.right}" \
                                f"{float_is_integer(tick.contract.strike)}"
                bid_size = int(tick.bidSize)
                otm = percent_diff(price, tick.contract.strike)
                dte = get_dte(option_symbol, tick.contract.right)
                # test
                init_margin = whatIfOrder(tick.contract, order)

                if dte <= DTE_MAX:
                    if tick.contract.right == 'P':
                        output.append(f'{BCOLORS.RED}{option_symbol : <15}{dte: ^10}{otm: ^10}{bid_size : ^10}{init_margin : >10}{BCOLORS.ENDC}')
                    if tick.contract.right == 'C':
                        output.append(f'{BCOLORS.CYAN}{option_symbol : <15}{dte: ^10}{otm: ^10}{bid_size : ^10}{init_margin : >10}{BCOLORS.ENDC}')

    ib.disconnect()


def main():

    logging.getLogger('ib_insync.wrapper').setLevel(logging.FATAL)

    while 1:
        tickers = get_tickers()
        ticker_batch = math.ceil(len(tickers) / THREADS)
        splits = grouper(ticker_batch, tickers)

        threads = []
        for array in splits:
            process_thread = Thread(target=process, args=(array,))
            threads.append(process_thread)
            process_thread.start()
            time.sleep(1)
        for thread in threads:
            thread.join()

        if len(output) > 1:
            print('\n'.join(output))

        del output[1:]

        print(f'Next run in {FREQUENCY} minutes...')
        time.sleep(FREQUENCY * 60)


# USER VARIABLES
PERCENT_OTM = 30
FREQUENCY = 5  # minutes to sleep before re-running
DTE_MAX = 11  # the furthest penny you want to farm
# END USER VARIABLES

# DO NOT EDIT -- unless you know what you're doing, but don't ping me on Discord about this
output = [f"{BCOLORS.HEADER}{'Symbol': <15}{'DTE': ^10}{'% OTM': ^10}{'Bid Size': ^10}{'Initial Margin': >10}{BCOLORS.ENDC}"]
THREADS = 8

# Start main() function
main()
