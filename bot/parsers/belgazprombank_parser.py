# coding: utf-8

import datetime

import requests
from bs4 import BeautifulSoup

from cache.mongo import MongoCurrencyCache
from currency import Currency
from settings import LOGGER_NAME, logger
from .base import BaseParser


class BelgazpromParser(BaseParser):

    BASE_URL = 'http://belgazprombank.by/about/kursi_valjut/'
    DATE_FORMAT = "%d.%m.%Y"
    name = 'Белгазпромбанк'
    short_name = 'bgp'
    MINIMAL_DATE = datetime.datetime(year=2004, month=5, day=1)
    allowed_currencies = ('USD', 'EUR', 'RUB', 'BYR',
                          'GBP', 'UAH', 'CHF', 'PLN')

    def __init__(self, *args, **kwargs):
        self.name = BelgazpromParser.name
        self.short_name = BelgazpromParser.short_name
        self._cache = MongoCurrencyCache(Currency, LOGGER_NAME)

    def __get_response_for_the_date(self, d):
        """Gets page with currency rates for the given date"""

        supplied_date = d
        if supplied_date is None:
            supplied_date = datetime.date.today()
        assert isinstance(supplied_date, datetime.date), "Incorrect date type"

        str_date = datetime.date.strftime(supplied_date,
                                          BelgazpromParser.DATE_FORMAT)
        date_params = {"date": str_date}
        return requests.get(BelgazpromParser.BASE_URL, params=date_params)

    def __soup_from_request(self, resp):
        """Create soup object from the supplied requests response"""
        text = resp.text
        return BeautifulSoup(text, "html.parser")

    def __get_currency_table(self, soup):
        """Returns table with exchanges rates from the given
        BeautifulSoup object"""
        return soup.find(id="courses_tab1_form").parent

    def __get_currency_objects(self, cur_table, days_since_now=None):
        """
            Parses BeautifulSoup table with exchanges rates and extracts
            currency data
        """
        if not days_since_now:
            exchange_table = cur_table.find('table').find('tbody')
            exchange_rows = exchange_table.find_all('tr')
            return [BelgazpromParser.__currency_object_from_row(row)
                    for row in exchange_rows]
        # TODO: add data display for the date in the past

    @classmethod
    def __currency_object_from_row(cls, row_object):
        table_cols = row_object.find_all('td')
        return Currency(name=table_cols[0].text.strip(),
                        iso=table_cols[1].text,
                        sell=table_cols[2].find(text=True),
                        buy=table_cols[3].find(text=True))

    def get_all_data(self):
        return [tuple(cur) for cur in self.currencies]

    def get_all_currencies(self, date=None):
        # TODO: check if string is supplied as date
        if date is None:
            date = datetime.date.today()
        assert isinstance(date, datetime.date), "Incorrect date supplied"

        r = self.__get_response_for_the_date(date)
        s = self.__soup_from_request(r)
        currency_table = self.__get_currency_table(s)
        currencies = self.__get_currency_objects(currency_table)

        str_date = date.strftime(BelgazpromParser.DATE_FORMAT)

        is_today = date == datetime.date.today()
        if not is_today:
            for currency in currencies:
                self._cache.cache_currency(self.short_name,
                                           currency,
                                           str_date)

        return currencies

    def get_currency_for_diff_date(self, diff_days, currency="USD"):
        former_date = datetime.date.today - datetime.timedelta(days=diff_days)
        return self.get_currency(currency, date=former_date)

    def get_currency(self, currency_name="USD", date=None):
        # TODO: requires heavy optimization or caching
        if date is None:
            date = datetime.date.today()
        assert isinstance(date, datetime.date), "Incorrect date supplied"

        is_today = date == datetime.date.today()

        str_date = date.strftime(BelgazpromParser.DATE_FORMAT)

        cached_item = None
        if not is_today:
            cached_item = self._cache.get_cached_value(self.short_name,
                                                       currency_name,
                                                       str_date)
        if cached_item:
            logger.info("Cached value found {}, returning".format(cached_item))
            return cached_item

        currencies = self.get_all_currencies(date)

        for cur in currencies:
            if currency_name.upper() == cur.iso:
                if not is_today:
                    self._cache.cache_currency(self.short_name, cur, str_date)
                return cur
        else:
            return Currency('NoValue', '', '', '')
