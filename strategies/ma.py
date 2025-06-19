# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple

"""
均值回归策略, 基于价格偏离度和动能反转的交易系统

需要的指标
    长期均线： EMA(50)
    震荡指标： RSI(14)
    波动率指标： ATR(14)

其余参数
    偏离度阈值： 2% (价格比EMA50低/高至少2%)
    ATR止损乘数： 2.0 (即2倍ATR止损)

做多
    价格偏离： 当前价格 低于 EMA(50)，且 (EMA(50) - Close) / EMA(50) ≥ 2%。
    动能反转： RSI(14) 从30以下超卖区 向上突破30。
    仓位： 根据价格偏离EMA(50)的程度动态调整仓位，偏离越大仓位越大（在最大风险承受范围内）。

多单止损
    动态止损： 止损价 = 入场价 - ATR(14) * 2.0。
    或 趋势逆转： 价格跌破入场K线最低点，或重新跌破EMA(50)并收盘其下方。
    或 最大亏损： 单笔亏损达到账户资金的某个百分比

多单止盈
    目标均线止盈（主要）： 价格 向上触及或突破EMA(50) 时，平仓大部分仓位（如80%）。
    追踪止盈（剩余仓位）： 剩余小部分仓位采用追踪止损 最高价 - ATR(14) * 1.0。
    固定盈亏比： 盈利达到止损的1.5倍或2倍时平仓。

做空
    价格偏离： 当前价格 高于 EMA(50)，且 (Close - EMA(50)) / EMA(50) ≥ 2%。
    动能反转： RSI(14) 从70以上超买区 向下突破70。
    仓位： 根据价格偏离EMA(50)的程度动态调整仓位，偏离越大仓位越大（在最大风险承受范围内）。

空单止损（必设）：
    动态止损： 止损价 = 入场价 + ATR(14) * 2.0。
    或 趋势逆转： 价格突破入场K线最高点，或重新突破EMA(50)并收盘其上方。
    或 最大亏损： 单笔亏损达到账户资金的某个百分比。

空单止盈（锁定利润）：
    目标均线止盈（主要）： 价格 向下触及或跌破EMA(50) 时，平仓大部分仓位（如80%）。
    追踪止盈（剩余仓位）： 剩余小部分仓位采用追踪止损 最低价 + ATR(14) * 1.0。
    或 固定盈亏比： 盈利达到止损的1.5倍或2倍时平仓。
"""



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
    AnnotationType,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib


class ma(IStrategy):
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
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

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.10

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
    
    ema_timeperiod = IntParameter(5, 100, default=50, space="buy")
    rsi_timeperiod = IntParameter(5, 50, default=14, space="buy")
    atr_length = IntParameter(5, 50, default=14, space="buy")
    atr_stoploss = DecimalParameter(1.0, 10.0, default=2.0, space="buy")
    price_delta = DecimalParameter(0.01, 0.5, default=0.02, space="buy")


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
            "main_plot": {
                "ema": {"color": "red"},
            },
            "subplots": {
                "RSI": {
                    "rsi": {"color": "red"},
                },
                "ATR": {
                    "atr": {"color": "blue"},
                }
            }
        }

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_timeperiod.value)
        # EMA - Exponential Moving Average
        dataframe["ema"] = ta.EMA(dataframe, timeperiod=self.ema_timeperiod.value)
        # ATR - Average True Range
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_length.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # long
        price_cond_long = (dataframe['close'] < dataframe['ema']) & \
            (((dataframe['ema'] - dataframe['close']) / dataframe['ema']) >= self.price_delta.value)

        rsi_cond_long = (dataframe['rsi'].shift(1) < self.buy_rsi.value) & \
            (dataframe['rsi'] >= self.buy_rsi.value)

        cond_long = (
            price_cond_long &
            rsi_cond_long
        )
        dataframe.loc[
            cond_long, ['enter_long', 'enter_tag']] = (1, 'buy_signal')
        
        # short
        price_cond_short = (dataframe['close'] > dataframe['ema']) & \
            (((dataframe['close'] - dataframe['ema']) / dataframe['ema']) >= self.price_delta.value)
        rsi_cond_short = (dataframe['rsi'].shift(1) > self.sell_rsi.value) & \
            (dataframe['rsi'] <= self.sell_rsi.value)
        cond_short = (
            price_cond_short &
            rsi_cond_short
        )
        dataframe.loc[
            cond_short, ['enter_short', 'enter_tag']] = (1, 'sell_signal')
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe