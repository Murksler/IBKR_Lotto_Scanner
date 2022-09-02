#!/usr/bin/env python3

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
... (61 Zeilen verbleibend)
