from pandas import DataFrame
from functools import reduce

import talib.abstract as ta

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)
import freqtrade.vendor.qtpylib.indicators as qtpylib

class MyAwesomeStrategy(IStrategy):
    stoploss = -0.05
    timeframe = '15m'
    # Define the parameter spaces
    # cooldown_lookback = IntParameter(2, 48, default=5, space="protection", optimize=True)
    # stop_duration = IntParameter(12, 200, default=5, space="protection", optimize=True)
    # use_stop_protection = BooleanParameter(default=True, space="protection", optimize=True)

    buy_adx = DecimalParameter(20, 40, decimals=1, default=30.1, space="buy")
    buy_rsi = IntParameter(20, 40, default=30, space="buy")
    buy_adx_enabled = BooleanParameter(default=True, space="buy")
    buy_rsi_enabled = CategoricalParameter([True, False], default=False, space="buy")
    buy_trigger = CategoricalParameter(["bb_lower", "macd_cross_signal"], default="bb_lower", space="buy")


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['rsi'] = ta.RSI(dataframe)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # GUARDS AND TRENDS
        if self.buy_adx_enabled.value:
            conditions.append(dataframe['adx'] > self.buy_adx.value)
        if self.buy_rsi_enabled.value:
            conditions.append(dataframe['rsi'] < self.buy_rsi.value)

        # TRIGGERS
        if self.buy_trigger.value == 'bb_lower':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband'])
        if self.buy_trigger.value == 'macd_cross_signal':
            conditions.append(qtpylib.crossed_above(
                dataframe['macd'], dataframe['macdsignal']
            ))

        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe


    # def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    #     conditions = []
    #     conditions.append(qtpylib.crossed_above(
    #         dataframe[f'ema_short_{self.buy_ema_short.value}'], dataframe[f'ema_long_{self.buy_ema_long.value}']
    #     ))
    #
    #     # Check that volume is not 0
    #     conditions.append(dataframe['volume'] > 0)
    #
    #     if conditions:
    #         dataframe.loc[
    #             reduce(lambda x, y: x & y, conditions),
    #             'enter_long'] = 1
    #     return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(qtpylib.crossed_above(
            dataframe[f'ema_long_{self.buy_ema_long.value}'], dataframe[f'ema_short_{self.buy_ema_short.value}']
        ))

        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1
        return dataframe
