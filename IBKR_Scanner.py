from ib_insync import *
from threading import Thread
from itertools import islice
import time
import random
import asyncio
import datetime
import os


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


def percent_diff(price, strike):

    return int((abs(price - strike) / price) * 100)


def float_is_integer(num):

    if num.is_integer():
        return int(num)

    return num


def get_dte(symbol_with_date, right):

    # print(f'get_dte(): {symbol_with_date}')

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


def process(tlist):

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    f = open('output.csv', 'a')

    ib = IB()
    client_id = random.randrange(1, 1000)
    try:
        ib.connect('127.0.0.1', 7496, readonly=True, clientId=client_id)
    except ConnectionRefusedError:
        print('Connection error')
        return

    # real time by default, 2 is frozen market data for testing
    ib.reqMarketDataType(3)

    output = []
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
        expirations = sorted(exp for exp in chain.expirations)[:1]
        rights = ['P','C']
        contracts = [Option(stock.symbol, expiration, strike, right, 'SMART')
                for right in rights
                for expiration in expirations
                for strike in strikes if right == 'P' and strike < price or right == 'C' and strike > price]
        contracts = ib.qualifyContracts(*contracts)

        # get the market data for all of these options contracts
        tickers = ib.reqTickers(*contracts)

        # print contracts if they have a bid size > 0
        for tick in tickers:
            if tick.bidSize > 0:
                symbol_date = datetime.datetime.strptime(tick.contract.lastTradeDateOrContractMonth, '%Y%m%d').strftime('%m%d%y')
                option_symbol = f"{tick.contract.symbol}_{symbol_date}{tick.contract.right}{float_is_integer(tick.contract.strike)}"
                bid_size = tick.bidSize
                otm = percent_diff(price, tick.contract.strike)
                dte = get_dte(option_symbol, tick.contract.right)
                f.write(f'Symbol: {option_symbol}\tDTE: {dte}\t%OTM: {otm}\tBid Size: {bid_size}\n')

    ib.disconnect()
    f.close()

def main():

    try:
        os.remove('output.csv')
    except FileNotFoundError:
        pass

    tickers = get_tickers()
    splits = grouper(20, tickers)

    for array in splits:
        process_thread = Thread(target=process, args=(array,))
        # process_thread.daemon = True
        process_thread.start()
        time.sleep(1)


##### USER VARIABLES #####
PERCENT_OTM = 30
##### END USER VARIABLES #####

# Start main() function
main()
