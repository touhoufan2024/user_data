# --- 保存为 sma_rsi_stack_partial_strategy_plot.py ---
# --- 放置于 user_data/strategies/ 目录下 ---

import logging
from typing import Optional, Dict, List
import pandas as pd
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
from datetime import datetime, timezone # 导入 timezone 用于 adjust_trade_position

# 设置日志记录器
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

class SmaRsiStackPartialStrategyPlot(IStrategy): # 类名稍作修改
    """
    策略逻辑 (带绘图):
    - 入场: SMA 金叉
    - 加仓: SMA 再次金叉
    - 部分出场: RSI > 70 (卖出 50%)
    - 完全出场: RSI > 90
    - 包含止损和绘图配置
    """
    INTERFACE_VERSION = 3

    # --- 策略配置 ---
    ticker_interval = '1h'
    minimal_roi = {"0": 1.0}
    stoploss = -0.10
    position_adjustment_enable = True

    # --- 指标参数 ---
    sma_fast_period = 20
    sma_slow_period = 50
    rsi_period = 14

    # --- 退出条件参数 ---
    rsi_partial_exit_level = 60
    rsi_full_exit_level = 75
    partial_exit_pct = 0.50

    # === 添加绘图配置 ===
    plot_config = {
        'main_plot': {
            'sma_fast': {'color': 'blue', 'type': 'line'},
            'sma_slow': {'color': 'orange', 'type': 'line'},
        },
        'subplots': {
            'RSI': {
                'rsi': {'color': 'purple'},
                # 添加 RSI=70 的水平线 (用于部分退出)
                'rsi_p_exit_line': {
                    'color': 'red',
                    'plotly': {'dash': 'dash'} # 设置为虚线
                 },
                 # 添加 RSI=90 的水平线 (用于完全退出)
                 'rsi_f_exit_line': {
                    'color': 'darkred', # 使用更深的红色区分
                    'plotly': {'dash': 'dot'} # 设置为点线
                 }
            },
            # 可以取消注释以绘制信号，但不推荐作为线图
            # 'Signals': {
            #     'signal_entry_stack': {'color': 'lightgreen'},
            #     'signal_exit_full_rsi': {'color': 'lightcoral'}
            # }
        }
    }
    # === 结束绘图配置 ===

    # --- 指标计算 (添加绘图辅助列) ---
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SMA 计算
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=self.sma_fast_period)
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=self.sma_slow_period)

        # RSI 计算
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # -- 生成信号列 --
        dataframe['signal_entry_stack'] = qtpylib.crossed_above(
            dataframe['sma_fast'], dataframe['sma_slow']
        ).astype(int)
        dataframe['signal_exit_full_rsi'] = (
            dataframe['rsi'] > self.rsi_full_exit_level
        ).astype(int)

        # -- 添加用于绘图的 RSI 水平线列 --
        dataframe['rsi_p_exit_line'] = self.rsi_partial_exit_level
        dataframe['rsi_f_exit_line'] = self.rsi_full_exit_level

        return dataframe

    # --- 初始入场逻辑 ---
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe['signal_entry_stack'] == 1,
            ['enter_long', 'enter_tag']
        ] = (1, 'SMA_Cross_Entry')
        logger.info(f"'{metadata}': Entry signal generated.")
        return dataframe

    # --- 完全出场逻辑 ---
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe['signal_exit_full_rsi'] == 1,
            ['exit_long', 'exit_tag']
        ] = (1, 'RSI_90_Full_Exit')
        return dataframe

    # --- 自定义初始金额 (可选) ---
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        return proposed_stake

    # --- 核心：自定义仓位调整 (加仓 & 部分平仓) ---
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        logger.info(f"'{trade.pair}': Adjusting trade position.")
        # (这里的代码与上一个版本完全相同，处理加仓和 RSI>70 部分退出逻辑)
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.ticker_interval)
        if dataframe.empty:
            logger.warning(f"'{trade.pair}': Analyzed dataframe empty in adjust_trade_position.") # 日志可能过多
            return None
        latest_candle = dataframe.iloc[-1].squeeze()
        current_rsi = latest_candle['rsi']

        # --- 1. 检查部分退出 (RSI > 70) ---
        try:
            partial_exit_done_flag = trade.custom_info.get('partial_exit_rsi70_done', False)

            if current_rsi > self.rsi_partial_exit_level and not partial_exit_done_flag:
                amount_to_sell = trade.amount * self.partial_exit_pct
                stake_amount_to_sell_value = amount_to_sell * current_rate
                if min_stake is not None and stake_amount_to_sell_value < min_stake:
                    logger.warning(f"'{trade.pair}': RSI > 70 Partial exit value below min_stake. Skipping.")
                    return None
                logger.info(f"'{trade.pair}': RSI > {self.rsi_partial_exit_level}. Partial exit: selling {self.partial_exit_pct:.0%}.")
                trade.custom_info['partial_exit_rsi70_done'] = True
                trade.update(trade.custom_info)
                return -stake_amount_to_sell_value
            elif current_rsi < self.rsi_partial_exit_level and partial_exit_done_flag:
                logger.info(f"'{trade.pair}': RSI fell below {self.rsi_partial_exit_level}. Resetting partial exit flag.")
                trade.custom_info['partial_exit_rsi70_done'] = False
                trade.update(trade.custom_info)
        except Exception as e:
            logger.error(f"'{trade.pair}': Error during RSI partial exit logic: {e}")
            return None

        # --- 2. 检查加仓 (如果没有执行部分退出) ---
        try:
            if latest_candle['signal_entry_stack'] == 1:
                stake_to_add = trade.stake_amount
                current_total_value = trade.amount * current_rate
                if (current_total_value + stake_to_add) > max_stake:
                    logger.warning(f"'{trade.pair}': Stacking would exceed max_stake. Skipping.")
                    return None
                if min_stake is not None and stake_to_add < min_stake:
                     logger.warning(f"'{trade.pair}': Stacking stake below min_stake. Skipping.")
                     return None
                logger.info(f"'{trade.pair}': SMA Cross signal. Stacking (adding stake): {stake_to_add:.4f}")
                trade.custom_info['stack_count'] = trade.custom_info.get('stack_count', 0) + 1
                trade.update(trade.custom_info)
                return stake_to_add
        except Exception as e:
            logger.error(f"'{trade.pair}': Error during stacking logic: {e}")
            return None

        # --- 3. 无操作 ---
        return None

# ... (类的结束) ...