# --- 保存为 simple_adjust_pos_strategy.py ---
# --- 放置于 user_data/strategies/ 目录下 ---

import logging
from typing import Optional, Dict, List
import pandas as pd
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
from datetime import datetime, timedelta, timezone # 导入 timedelta 和 timezone

# 设置日志记录器
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # 取消注释以启用基本日志输出

class SimpleAdjustPosStrategy(IStrategy):
    """
    一个简单的策略，主要逻辑在 adjust_trade_position 中：
    - 初始入场: SMA 5 穿越 SMA 20
    - 定时加仓: 如果交易亏损且距离上次加仓/开仓超过 N 小时，则加仓。
    - 退出: 依赖 ROI 和止损。
    """
    INTERFACE_VERSION = 3

    # --- 策略配置 ---
    ticker_interval = '1h'  # 时间框架
    # 需要设置 ROI，作为主要的盈利退出方式
    minimal_roi = {
        "0": 0.10  # 10% 盈利目标
    }
    # 止损是必须的!
    stoploss = -0.10  # 10% 止损

    # --- 指标参数 ---
    sma_fast_period = 5   # 使用较快的 SMA 增加信号频率
    sma_slow_period = 20

    # --- 自定义加仓参数 ---
    dca_interval_hours = 24   # 加仓时间间隔 (小时)
    dca_stake_multiplier = 1.0 # 每次加仓金额 = 初始金额 * 1.0
    dca_max_entries = 3      # 最大加仓次数

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
        """简单的首次开仓信号"""
        dataframe.loc[
            dataframe['signal_entry'] == 1,
            ['enter_long', 'enter_tag']
        ] = (1, 'SMA_Cross_Entry')
        return dataframe

    # --- 出场逻辑 (主要依赖 ROI/Stoploss) ---
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """可以留空，主要依赖 ROI 和止损退出"""
        # 如果需要，也可以添加基于指标的退出信号
        # dataframe.loc[condition, ['exit_long', 'exit_tag']] = (1, 'Exit_Signal')
        return dataframe

    # --- 自定义初始金额 ---
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        return proposed_stake

    # --- 核心：简单的定时亏损加仓逻辑 ---
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        简单的 adjust_trade_position 示例：
        如果交易亏损，并且距离上次加仓（或开仓）时间超过设定间隔，则执行加仓。
        """
        # 获取加仓次数和上次加仓时间的状态
        dca_count = trade.custom_info.get('dca_count', 0)
        last_dca_time_str = trade.custom_info.get('last_dca_time')
        last_dca_time = None
        if last_dca_time_str:
            last_dca_time = datetime.fromisoformat(last_dca_time_str)
            if last_dca_time.tzinfo is None: # 确保时区一致性
                last_dca_time = last_dca_time.replace(tzinfo=timezone.utc)

        # 检查是否已达到最大加仓次数
        if dca_count >= self.dca_max_entries:
            # logger.debug(f"'{trade.pair}': Max DCA entries ({self.dca_max_entries}) reached.")
            return None

        # 确保 current_time 是 aware 的
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # 确定计算时间间隔的参考点（上次加仓时间或开仓时间）
        reference_time = last_dca_time if last_dca_time else trade.open_date_utc
        if reference_time.tzinfo is None: # 确保开仓时间也是 aware 的
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # 计算距离上次事件过去了多久
        time_since_last_event = current_time - reference_time
        required_interval = timedelta(hours=self.dca_interval_hours)

        # 检查条件：亏损 + 时间间隔达到 + 未超最大次数
        if current_profit < 0 and time_since_last_event >= required_interval:
            try:
                # 计算加仓金额
                stake_to_add = trade.stake_amount * self.dca_stake_multiplier

                # 检查最小/最大金额限制
                current_total_value = trade.amount * current_rate
                if (current_total_value + stake_to_add) > max_stake:
                    logger.warning(f"'{trade.pair}': Timed DCA order ({stake_to_add:.4f}) would exceed max_stake "
                                   f"({max_stake:.4f}). Current value: {current_total_value:.4f}. Skipping.")
                    return None
                if min_stake is not None and stake_to_add < min_stake:
                     logger.warning(f"'{trade.pair}': Timed DCA order stake ({stake_to_add:.4f}) "
                                    f"below min_stake ({min_stake:.4f}). Skipping.")
                     return None

                logger.info(
                    f"'{trade.pair}': Trade in loss ({current_profit:.2%}) for >= {self.dca_interval_hours} hours. "
                    f"Executing timed DCA ({dca_count + 1}/{self.dca_max_entries}). Adding stake: {stake_to_add:.4f}"
                )

                # 更新状态信息
                trade.custom_info['dca_count'] = dca_count + 1
                trade.custom_info['last_dca_time'] = current_time.isoformat() # 记录本次加仓时间
                trade.update(trade.custom_info)

                # 返回正数金额以执行加仓
                return stake_to_add

            except Exception as e:
                logger.error(f"'{trade.pair}': Error during timed DCA logic: {e}")
                return None

        # 如果条件不满足，则不进行任何操作
        return None