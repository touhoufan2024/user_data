from freqtrade.strategy import IStrategy
from typing import Dict, List
from pandas import DataFrame
import talib

class SimpleMACrossoverStrategy(IStrategy):
    """
    一个简单的基于均线交叉的 Freqtrade 策略。
    """

    # 策略设置
    timeframe = '5m'  # 交易时间框架
    stoploss = -0.03  # 止损百分比 (例如 -3%)
    takeprofit = 0.05 # 止盈百分比 (例如 5%)

    # 指标设置
    short_period = 20  # 短期 SMA 周期
    long_period = 50   # 长期 SMA 周期

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        添加策略所需的指标。
        """
        dataframe['sma_short'] = talib.SMA(dataframe['close'], timeperiod=self.short_period)
        dataframe['sma_long'] = talib.SMA(dataframe['close'], timeperiod=self.long_period)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        定义买入信号的条件。
        """
        conditions = (
            (dataframe['sma_short'] > dataframe['sma_long']) &  # 短期 SMA 上穿长期 SMA
            (dataframe['sma_short'].shift(1) <= dataframe['sma_long'].shift(1)) # 前一根 K 线短期 SMA 在长期 SMA 下方或相等
        )
        dataframe.loc[conditions, 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        定义卖出信号的条件。
        """
        conditions = (
            (dataframe['sma_short'] < dataframe['sma_long']) &  # 短期 SMA 下穿长期 SMA
            (dataframe['sma_short'].shift(1) >= dataframe['sma_long'].shift(1)) # 前一根 K 线短期 SMA 在长期 SMA 上方或相等
        )
        dataframe.loc[conditions, 'sell'] = 1
        return dataframe

# 为了在没有 Freqtrade 环境的情况下运行和测试策略逻辑，您可以添加以下代码：
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

    # 创建策略实例
    strategy = SimpleMACrossoverStrategy()

    # 计算指标
    df = strategy.populate_indicators(df.copy(), {})
    print("带有指标的 DataFrame (尾部):")
    print(df.tail())

    # 生成买入信号
    buy_df = strategy.populate_buy_trend(df.copy(), {})
    print("\n带有买入信号的 DataFrame (前几个):")
    print(buy_df[buy_df['buy'] == 1].head())

    # 生成卖出信号
    sell_df = strategy.populate_sell_trend(df.copy(), {})
    print("\n带有卖出信号的 DataFrame (前几个):")
    print(sell_df[sell_df['sell'] == 1].head())

