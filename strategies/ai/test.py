# --- 请将此文件保存为 strategy_name.py (例如: sma_cross_strategy.py) ---
# --- 并将其放置在 Freqtrade 用户目录的 strategies 文件夹下 ---

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame

class SimpleSMACrossover(IStrategy):
    """
    一个简单的移动平均线交叉策略
    买入: 当短期 SMA 向上穿越长期 SMA 时
    卖出: 当短期 SMA 向下穿越长期 SMA 时
    """
    # --- 策略配置 ---
    # 策略的自定义信息，可选
    INTERFACE_VERSION = 3

    # 时间框架 (Timeframe) - 建议根据交易对和市场情况选择
    # 例如: '1m', '5m', '15m', '30m', '1h', '4h', '1d'
    ticker_interval = '1h'

    # 最小盈利设置 (Minimal ROI)
    # 这是一个字典，定义了持仓多久后期望达到的最小盈利百分比
    # 例如: 60 分钟后盈利 1%，120 分钟后盈利 2%
    # 键是分钟数，值是百分比 (例如 0.01 代表 1%)
    minimal_roi = {
        "60": 0.01,  # 1% profit after 60 minutes
        "120": 0.02, # 2% profit after 120 minutes
        "0": 0.04    # 4% profit after any duration > 120 minutes (0 means "infinite")
    }

    # 止损设置 (Stoploss)
    # 设置一个固定的止损百分比
    # 例如: -0.10 代表亏损 10% 时自动卖出
    stoploss = -0.10

    # 尾随止损 (Trailing Stoploss) - 可选
    # 如果启用，当价格上涨时，止损位也会随之提高
    # trailing_stop = True
    # trailing_stop_positive = 0.01  # 当盈利达到 1% 时开始尾随
    # trailing_stop_positive_offset = 0.02 # 保持盈利回撤 2% 时触发止损
    # trailing_only_offset_is_reached = True # 仅当盈利达到 offset 时才开始尾随

    # --- 指标定义 ---
    # 定义短期和长期 SMA 的周期
    sma_short_period = 20
    sma_long_period = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算策略所需的指标

        :param dataframe: Freqtrade 提供的包含市场数据的 Pandas DataFrame
        :param metadata: 包含交易对信息的字典
        :return: 包含计算后指标的 DataFrame
        """
        # 计算短期 SMA
        dataframe[f'sma_{self.sma_short_period}'] = ta.SMA(dataframe, timeperiod=self.sma_short_period)
        # 计算长期 SMA
        dataframe[f'sma_{self.sma_long_period}'] = ta.SMA(dataframe, timeperiod=self.sma_long_period)

        print(f"Calculated indicators for {metadata['pair']}") # 简单打印日志，确认指标计算
        # print(dataframe.tail()) # 可以取消注释以查看最后几行数据和指标

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号逻辑

        :param dataframe: 包含指标的 DataFrame
        :param metadata: 包含交易对信息的字典
        :return: 包含买入信号 ('buy' 列) 的 DataFrame
        """
        # 设置买入条件：短期 SMA 向上穿越长期 SMA
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe[f'sma_{self.sma_short_period}'], dataframe[f'sma_{self.sma_long_period}'])
            ),
            'buy'] = 1 # 将 'buy' 列设置为 1 表示买入信号

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号逻辑

        :param dataframe: 包含指标的 DataFrame
        :param metadata: 包含交易对信息的字典
        :return: 包含卖出信号 ('sell' 列) 的 DataFrame
        """
        # 设置卖出条件：短期 SMA 向下穿越长期 SMA
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe[f'sma_{self.sma_short_period}'], dataframe[f'sma_{self.sma_long_period}'])
            ),
            'sell'] = 1 # 将 'sell' 列设置为 1 表示卖出信号

        return dataframe