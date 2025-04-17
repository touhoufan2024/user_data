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

    timeframe = "15m"

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

    # raindow lines
    x1 = DecimalParameter(0.1, 10, default=12, space="raindow")
    x2 = DecimalParameter(0.1, 10, default=8.5, space="raindow")
    x3 = DecimalParameter(0.1, 10, default=6.8, space="raindow")
    x4 = DecimalParameter(0.1, 10, default=5, space="raindow")
    x5 = DecimalParameter(0.1, 10, default=0, space="raindow")
    x6 = DecimalParameter(0.1, 10, default=-5, space="raindow")
    x7 = DecimalParameter(0.1, 10, default=-6.8, space="raindow")
    x8 = DecimalParameter(0.1, 10, default=-8.5, space="raindow")
    x9 = DecimalParameter(0.1, 10, default=-12, space="raindow")


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
                # "hlc3_ma": {"color": "red"},
                # "tr_ma": {"color": "blue"}
                "line1": {"color": "orange"},
                "line2": {"color": "yellow"},
                "line3": {"color": "lightgreen"},
                "line4": {"color": "lightblue"},
                "line5": {"color": "darkblue"},
                "line6": {"color": "mediumpurple"},
                "line7": {"color": "teal"},
                "line8": {"color": "lightpink"},
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
        dataframe["hlc3"] = ((dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3).astype(float)
        dataframe["hlc3_ma"] = ta.WMA(dataframe["hlc3"], timeperiod= self.raindow_length.value)

        dataframe['tr'] = ta.TRANGE(dataframe['high'], dataframe['low'], dataframe['close'])
        dataframe["tr_ma"] = ta.WMA(dataframe["tr"], timeperiod= self.raindow_length.value)
        
        dataframe["high_ma"] = ta.WMA(dataframe["high"], timeperiod= self.raindow_length.value)
        dataframe["low_ma"] = ta.WMA(dataframe["low"], timeperiod= self.raindow_length.value)

        dataframe['line1'] = dataframe["low_ma"] + self.x1.value * dataframe["tr_ma"]
        dataframe['line2'] = dataframe["low_ma"] + self.x2.value * dataframe["tr_ma"]
        dataframe['line3'] = dataframe["low_ma"] + self.x3.value * dataframe["tr_ma"]
        dataframe['line4'] = dataframe["low_ma"] + self.x4.value * dataframe["tr_ma"]
        dataframe["line5"] = dataframe["hlc3_ma"]
        dataframe['line6'] = dataframe["high_ma"] + self.x6.value * dataframe["tr_ma"]
        dataframe['line7'] = dataframe["high_ma"] + self.x7.value * dataframe["tr_ma"]
        dataframe['line8'] = dataframe["high_ma"] + self.x8.value * dataframe["tr_ma"]
        dataframe['line9'] = dataframe["high_ma"] + self.x9.value * dataframe["tr_ma"]

        return dataframe

    # 开多  下穿 6 7 8 9
    # 开空 上穿  4 3 2 1
    # 离场 分批离场, 每批25%
    # 平空 下穿 5 6 7 8
    # 平多 上穿 5 4 3 2

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """

        longEntryCondition = (
            (qtpylib.crossed_below(dataframe["low"],dataframe["line6"])) &
            (qtpylib.crossed_below(dataframe["low"],dataframe["line7"])) &
            (qtpylib.crossed_below(dataframe["low"],dataframe["line8"])) &
            (qtpylib.crossed_below(dataframe["low"],dataframe["line9"])) &
            (dataframe["volume"] > 0)  # Make sure Volume is not 0
        )

        shortEntryCondition = (
            (qtpylib.crossed_above(dataframe["high"],dataframe["line4"])) &
            (qtpylib.crossed_above(dataframe["high"],dataframe["line3"])) &
            (qtpylib.crossed_above(dataframe["high"],dataframe["line2"])) &
            (qtpylib.crossed_above(dataframe["high"],dataframe["line1"])) &
            (dataframe["volume"] > 0)  # Make sure Volume is not 0
        )


        dataframe.loc[
            longEntryCondition,
            ["enter_long", "enter_tag"]] = (1, "long")
        dataframe.loc[
            shortEntryCondition,
            ["enter_short", "enter_tag"]] = (1, "short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        cond5 = (
            (qtpylib.crossed_above(dataframe["high"],dataframe["line5"])) &
            (qtpylib.crossed_below(dataframe["low"],dataframe["line5"])) &
            (dataframe["volume"] > 0)  # Make sure Volume is not 0
        )

        dataframe.loc[
            cond5,
            ["exit_long", "exit_tag"]] = (1, "exit_long")

        dataframe.loc[
            cond5,
            ["exit_short", "exit_tag"]] = (1, "exit_short")

        return dataframe


if __name__ == '__main__':
    import pandas as pd
    import numpy as np

    # 创建一个模拟的 DataFrame
    length = 100
    data = {
        'close': np.random.rand(length) * 100,
        'open': np.random.rand(length) * 100,
        'high': np.random.rand(length) * 100,
        'low': np.random.rand(length) * 100,
        'volume': np.random.rand(length) * 1000
    }
    df = pd.DataFrame(data)

    myconfig = {} # 这里可以添加配置参数
    # 创建策略实例
    strategy = raindow(config=myconfig)

    # 计算指标
    df = strategy.populate_indicators(df.copy(), {})
    print("带有指标的 DataFrame (尾部):")
    print(df.tail())

    # 生成买入信号
    # buy_df = strategy.populate_buy_trend(df.copy(), {})
    # print("\n带有买入信号的 DataFrame (前几个):")
    # print(buy_df[buy_df['buy'] == 1].head())

    # 生成卖出信号
    # sell_df = strategy.populate_sell_trend(df.copy(), {})
    # print("\n带有卖出信号的 DataFrame (前几个):")
    # print(sell_df[sell_df['sell'] == 1].head())