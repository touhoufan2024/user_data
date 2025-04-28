# --- 保存为 simple_dca_strategy_plot.py ---
# --- 放置于 user_data/strategies/ 目录下 ---

import logging
from typing import Optional, Dict, List
import pandas as pd
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
from datetime import datetime, timedelta, timezone

# 设置日志记录器
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

class SimpleDcaStrategyPlot(IStrategy): # 类名稍作修改
    """
    一个简单的 DCA 策略 (带绘图配置)，使用 adjust_trade_position 实现：
    - 入场: SMA 金叉
    - 加仓: 当亏损达到阈值且满足冷却条件时，执行 DCA 加仓。
    - 退出: 依赖 ROI 和 止损。
    """
    INTERFACE_VERSION = 3

    # --- 策略配置 ---
    ticker_interval = '1h'
    minimal_roi = {"0": 0.10}
    stoploss = -0.20

    # --- 指标参数 ---
    sma_fast_period = 20
    sma_slow_period = 50

    # --- DCA 参数 ---
    dca_min_profit_trigger = DecimalParameter(-0.10, -0.02, default=-0.05, decimals=2, space="buy")
    dca_stake_multiplier = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")
    dca_max_entries = IntParameter(1, 5, default=3, space="buy")
    dca_cooldown_minutes = IntParameter(30, 240, default=60, space="buy")

    position_adjustment_enable = True
    # === 添加绘图配置 ===
    plot_config = {
        'main_plot': {
            # 绘制快速 SMA 线 (蓝色)
            'sma_fast': {'color': 'blue'},
            # 绘制慢速 SMA 线 (橙色)
            'sma_slow': {'color': 'orange'},
        },
        'subplots': {
            # 本策略的核心 DCA 逻辑不依赖子图指标 (如 RSI)，所以这里留空
            # 如果后续添加了其他指标，可以在这里配置
            # "OtherIndicator": {
            #     'indicator_column': {'color': 'green'}
            # }
        }
    }
    # === 结束绘图配置 ===

    # --- 指标计算 ---
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=self.sma_fast_period)
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=self.sma_slow_period)

        # -- 生成入场信号列 --
        dataframe['signal_entry'] = qtpylib.crossed_above(
            dataframe['sma_fast'], dataframe['sma_slow']
        ).astype(int)

        return dataframe

    # --- 初始入场逻辑 ---
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe['signal_entry'] == 1,
            ['enter_long', 'enter_tag']
        ] = (1, 'SMA_Cross_Entry')
        return dataframe

    # --- 出场逻辑 (主要依赖 ROI/Stoploss) ---
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """留空，主要依赖 ROI 和止损退出"""
        return dataframe

    # --- 自定义初始金额 ---
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        return proposed_stake

    # --- 核心：DCA 逻辑 ---
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        简单的 adjust_trade_position DCA 逻辑：
        如果交易亏损达到阈值，并且满足冷却和次数限制，则执行加仓。
        """
        # 从参数空间获取当前的 DCA 设置值
        dca_min_profit = self.dca_min_profit_trigger.value
        stake_multiplier = self.dca_stake_multiplier.value
        max_dca_entries = self.dca_max_entries.value
        dca_cooldown = timedelta(minutes=self.dca_cooldown_minutes.value)

        # 获取当前 DCA 状态
        dca_count = trade.custom_info.get('dca_count', 0)
        last_dca_time_str = trade.custom_info.get('last_dca_time')
        last_dca_time = None
        if last_dca_time_str:
            last_dca_time = datetime.fromisoformat(last_dca_time_str)
            if last_dca_time.tzinfo is None:
                last_dca_time = last_dca_time.replace(tzinfo=timezone.utc)

        # 检查是否已达到最大加仓次数
        if dca_count >= max_dca_entries:
            # logger.debug(f"'{trade.pair}': Max DCA entries ({max_dca_entries}) reached.")
            return None

        # 确保 current_time 是 aware 的
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # 确定冷却时间参考点
        reference_time = last_dca_time if last_dca_time else trade.open_date_utc
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # 检查冷却时间是否已过
        if current_time < (reference_time + dca_cooldown):
            # logger.debug(f"'{trade.pair}': DCA cooldown active until {reference_time + dca_cooldown}.")
            return None

        # 检查核心条件：当前利润率是否低于触发阈值
        if current_profit < dca_min_profit:
            try:
                # 计算加仓金额
                stake_to_add = trade.stake_amount * stake_multiplier

                # 检查最小/最大金额限制
                current_total_value = trade.amount * current_rate
                if (current_total_value + stake_to_add) > max_stake:
                    logger.warning(f"'{trade.pair}': DCA order ({stake_to_add:.4f}) would exceed max_stake "
                                   f"({max_stake:.4f}). Current value: {current_total_value:.4f}. Skipping.")
                    return None
                if min_stake is not None and stake_to_add < min_stake:
                     logger.warning(f"'{trade.pair}': DCA order stake ({stake_to_add:.4f}) "
                                    f"below min_stake ({min_stake:.4f}). Skipping.")
                     return None

                logger.info(
                    f"'{trade.pair}': Profit ({current_profit:.2%}) < Trigger ({dca_min_profit:.2%}) "
                    f"and Cooldown passed. Executing DCA ({dca_count + 1}/{max_dca_entries}). "
                    f"Adding stake: {stake_to_add:.4f}"
                )

                # 更新状态信息
                trade.custom_info['dca_count'] = dca_count + 1
                trade.custom_info['last_dca_time'] = current_time.isoformat() # 记录本次加仓时间
                trade.update(trade.custom_info)

                # 返回正数金额以执行加仓
                return stake_to_add

            except Exception as e:
                logger.error(f"'{trade.pair}': Error during DCA logic in adjust_trade_position: {e}")
                return None

        # 如果条件不满足 (例如利润不够低)，则不进行任何操作
        return None
