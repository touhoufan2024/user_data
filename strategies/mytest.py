import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple
import logging
from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)
import talib.abstract as ta
from technical import qtpylib
# 设置日志记录器
logger = logging.getLogger(__name__)

class mytest(IStrategy):
    # Strategy interface version - allow new iterations of the strategy interface.
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short: bool = True
    position_adjustment_enable = True
    grid_size = IntParameter(3, 10, default=5, space="buy", optimize=True)
    ma_period = IntParameter(20, 100, default=50, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(0.5, 3.0, default=1.5, space="buy", optimize=True)
    atr_period = DecimalParameter(5, 100, default=14, space="atr", optimize=True)
    minimal_roi = {"60": 0.01, "30": 0.02, "0": 0.04}
    stoploss = -0.10
    trailing_stop = False
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count: int = 30
    order_types = {"entry": "limit", "exit": "limit", "stoploss": "market", "stoploss_on_exchange": False}
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.plot_config = {
            'main_plot': {
                'mid_line': {'color': 'blue'},
            },
            'subplots': {
                "ATR": {
                    'atr': {'color': 'orange'},
                },
            },
        }
        for i in range(1, self.grid_size.value + 1):
            self.plot_config['main_plot'][f"grid_upper_{i}"] = {'color': 'green'}
            self.plot_config['main_plot'][f"grid_lower_{i}"] = {'color': 'red'}

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, self.atr_period.value)
        dataframe["mid_line"] = ta.EMA(dataframe["close"], self.ma_period.value)
        for i in range(1, self.grid_size.value + 1):
            dataframe[f"grid_upper_{i}"] = dataframe["mid_line"] + i * self.atr_multiplier.value * dataframe["atr"]
            dataframe[f"grid_lower_{i}"] = dataframe["mid_line"] - i * self.atr_multiplier.value * dataframe["atr"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for i in range(1, self.grid_size.value + 1):
            cond_long = (
                qtpylib.crossed_below(dataframe['close'], dataframe[f'grid_lower_{i}']) &
                (dataframe['close'] < dataframe['mid_line'])
            )
            dataframe.loc[
                cond_long, ['enter_long', 'enter_tag']] = (1, f'grid_long{i}')

            cond_short = (
                qtpylib.crossed_above(dataframe['close'], dataframe[f'grid_upper_{i}']) &
                (dataframe['close'] > dataframe['mid_line'])
            )
            dataframe.loc[
                cond_short, ['enter_short', 'entry_tag']] = (1, f'grid_short{i}')
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe


    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        logger.info(
            f"custom_stake_amount called with: pair={pair}, current_time={current_time}, "
            f"current_rate={current_rate}, proposed_stake={proposed_stake}, min_stake={min_stake}, "
            f"max_stake={max_stake}, leverage={leverage}, entry_tag={entry_tag}, side={side}, kwargs={kwargs}"
        )
        return proposed_stake

    # useless functions
    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """
        Called at the start of the bot iteration (one loop).
        Might be used to perform pair-independent tasks
        (e.g. gather some remote resource for comparison)

        For full documentation please go to https://www.freqtrade.io/en/latest/strategy-advanced/

        When not implemented by a strategy, this simply does nothing.
        :param current_time: datetime object, containing the current datetime
        :param **kwargs: Ensure to keep this here so updates to this won't break your strategy.
        """
        pass

    def custom_entry_price(
        self,
        pair: str,
        trade: Trade | None,
        current_time: datetime,
        proposed_rate: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return proposed_rate

    def adjust_order_price(
        self,
        trade: Trade,
        order: Order | None,
        pair: str,
        current_time: datetime,
        proposed_rate: float,
        current_order_rate: float,
        entry_tag: str | None,
        side: str,
        is_entry: bool,
        **kwargs,
    ) -> float | None:
        return current_order_rate

    def custom_exit_price(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        proposed_rate: float,
        current_profit: float,
        exit_tag: str | None,
        **kwargs,
    ) -> float:
        return proposed_rate


    use_custom_stoploss = True

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        pass

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | bool | None:
        return None

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        return True

    def check_entry_timeout(
        self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs
    ) -> bool:
        return False

    def check_exit_timeout(
        self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs
    ) -> bool:
        return False

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None | tuple[float | None, str | None]:
        return None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return 1.0

    def order_filled(
        self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs
    ) -> None:
        pass