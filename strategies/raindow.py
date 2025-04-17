# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class raindow(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "5m"

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    stoploss = -0.20

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Strategy parameters
    buy_rsi = IntParameter(10, 40, default=30, space="buy")
    sell_rsi = IntParameter(60, 90, default=70, space="sell")# Optional order type mapping.

    raindow_length = IntParameter(1, 999, default=200, space="raindow")

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Optional order time in force.
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }
    @property
    def plot_config(self):
        return {
            # Main plot indicators (Moving averages, ...)
            "main_plot": {
                # "tema": {},
                # "raindow_ma": {"color": '#d5de2f'},
                # "hlc3_ma": {"color": "red"},
                # "tr_ma": {"color": "blue"}
                "line1": {"color": "red"},
                "line2": {"color": "red"},
                "line3": {"color": "red"},
                "line4": {"color": "red"},
                "line5": {"color": "yellow"},
                "line6": {"color": "red"},
                "line7": {"color": "red"},
                "line8": {"color": "red"},
                "line9": {"color": "red"},
            },
            "subplots": {
                # Subplots - each dict defines one additional plot
                "MACD": {
                    "macd": {"color": "blue"},
                    "macdsignal": {"color": "orange"},
                },
                "RSI": {
                    "rsi": {"color": "red"},
                }
            }
        }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]


        # TEMA - Triple Exponential Moving Average
        dataframe["tema"] = ta.TEMA(dataframe, timeperiod=9)


        # Retrieve best bid and best ask from the orderbook
        # ------------------------------------
        """
        # first check if dataprovider is available
        if self.dp:
            if self.dp.runmode.value in ("live", "dry_run"):
                ob = self.dp.orderbook(metadata["pair"], 1)
                dataframe["best_bid"] = ob["bids"][0][0]
                dataframe["best_ask"] = ob["asks"][0][0]
        """

        # raindow
        dataframe["raindow_ma"] = ta.WMA(dataframe, timeperiod= self.raindow_length.value)
        
        dataframe["hlc3"] = ((dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3).astype(float)
        dataframe["hlc3_ma"] = ta.WMA(dataframe["hlc3"], timeperiod= self.raindow_length.value)

        dataframe['tr'] = ta.TRANGE(dataframe['high'], dataframe['low'], dataframe['close'])
        dataframe["tr_ma"] = ta.WMA(dataframe["tr"], timeperiod= self.raindow_length.value)
        
        dataframe["high_ma"] = ta.WMA(dataframe["high"], timeperiod= self.raindow_length.value)
        dataframe["low_ma"] = ta.WMA(dataframe["low"], timeperiod= self.raindow_length.value)

        dataframe['line1'] = dataframe["low_ma"] + 10 * dataframe["tr_ma"]
        dataframe['line2'] = dataframe["low_ma"] + 7.3 * dataframe["tr_ma"]
        dataframe['line3'] = dataframe["low_ma"] + 5 * dataframe["tr_ma"]
        dataframe['line4'] = dataframe["low_ma"] + 3.65 * dataframe["tr_ma"]
        dataframe["line5"] = dataframe["hlc3_ma"]
        dataframe['line6'] = dataframe["high_ma"] + (-3.65) * dataframe["tr_ma"]
        dataframe['line7'] = dataframe["high_ma"] + (-5) * dataframe["tr_ma"]
        dataframe['line8'] = dataframe["high_ma"] + (-7.3) * dataframe["tr_ma"]
        dataframe['line9'] = dataframe["high_ma"] + (-10) * dataframe["tr_ma"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        # dataframe.loc[
        #     (
        #         (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value)) &  # Signal: RSI crosses above buy_rsi
        #         (dataframe["tema"] <= dataframe["bb_middleband"]) &  # Guard: tema below BB middle
        #         (dataframe["tema"] > dataframe["tema"].shift(1)) &  # Guard: tema is raising
        #         (dataframe["volume"] > 0)  # Make sure Volume is not 0
        #     ),
        #     "enter_long"] = 1

        dataframe.loc[
            (
                    (qtpylib.crossed_below(dataframe["low"],dataframe["line9"])) &  # below line9, and entry long
                    (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            ["enter_long", "enter_tag"]] = (1, "long9")
        dataframe.loc[
            (
                    (qtpylib.crossed_above(dataframe["high"],dataframe["line1"])) &  # below line9, and entry long
                    (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            ["enter_exit", "enter_tag"]] = (1, "short1")
        # Uncomment to use shorts (Only used in futures/margin mode. Check the documentation for more info)
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value)) &  # Signal: RSI crosses above sell_rsi
                (dataframe["tema"] > dataframe["bb_middleband"]) &  # Guard: tema above BB middle
                (dataframe["tema"] < dataframe["tema"].shift(1)) &  # Guard: tema is falling
                (dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            'enter_short'] = 1
        """

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        # dataframe.loc[
        #     (
        #         (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value)) &  # Signal: RSI crosses above sell_rsi
        #         (dataframe["tema"] > dataframe["bb_middleband"]) &  # Guard: tema above BB middle
        #         (dataframe["tema"] < dataframe["tema"].shift(1)) &  # Guard: tema is falling
        #         (dataframe["volume"] > 0)  # Make sure Volume is not 0
        #     ),
        #     "exit_long"] = 1

        dataframe.loc[
            (
                    (qtpylib.crossed_above(dataframe["high"],dataframe["line8"])) &  # below line9, and entry long
                    (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            ["exit_long", "exit_tag"]] = (1, "exit_long9")

        dataframe.loc[
            (
                    (qtpylib.crossed_below(dataframe["low"],dataframe["line2"])) &  # below line9, and entry long
                    (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            ["exit_short", "exit_tag"]] = (1, "exit_short1")

        # Uncomment to use shorts (Only used in futures/margin mode. Check the documentation for more info)
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value)) &  # Signal: RSI crosses above buy_rsi
                (dataframe["tema"] <= dataframe["bb_middleband"]) &  # Guard: tema below BB middle
                (dataframe["tema"] > dataframe["tema"].shift(1)) &  # Guard: tema is raising
                (dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            'exit_short'] = 1
        """
        return dataframe