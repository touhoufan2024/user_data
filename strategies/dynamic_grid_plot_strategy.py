import numpy as np
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
from functools import reduce # 用于合并多个条件

class DynamicGridV3PlotStrategy(IStrategy):
    """
    Freqtrade (v3 Interface) 动态网格策略示例
    - 使用 populate_entry_trend / populate_exit_trend
    - 网格线添加到 DataFrame 以供绘图
    - 简化的入场/出场逻辑 (基于穿越网格线)

    如何绘图:
    freqtrade plot-dataframe --strategy DynamicGridV3PlotStrategy --timerange=YYYYMMDD-YYYYMMDD
    """
    INTERFACE_VERSION = 3

    # --- 策略参数 ---
    # ROI 和止损设置 (根据需要调整)
    minimal_roi = {
        "0": 0.1,   # 0分钟后，盈利10%则退出
        "30": 0.05, # 30分钟后，盈利5%则退出
        "60": 0.01  # 60分钟后，盈利1%则退出
    }
    stoploss = -0.10 # 10% 止损
    trailing_stop = False # 可以选择性启用追踪止损

    # 时间框架
    timeframe = '5m'

    # 订单类型设置
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # --- 网格参数 (可优化) ---
    grid_center_ema_period = IntParameter(10, 50, default=20, space="buy", optimize=True)
    grid_atr_period = IntParameter(10, 30, default=14, space="buy", optimize=True)
    grid_step_multiplier = DecimalParameter(0.5, 3.0, default=1.0, decimals=1, space="buy", optimize=True)
    grid_levels = IntParameter(2, 8, default=3, space="buy", optimize=True) # 中心线上下各 N 条

    # --- Freqtrade 绘图配置 ---
    plot_config = {
        'main_plot': {
            'ema_center': {'color': 'orange', 'linewidth': 1.5},
            # 只绘制最重要的几条网格以保持清晰度
            'sell_grid_1': {'color': 'red', 'linestyle': '--', 'linewidth': 1},
            'buy_grid_1': {'color': 'green', 'linestyle': '--', 'linewidth': 1},
            'sell_grid_2': {'color': 'salmon', 'linestyle': ':', 'linewidth': 0.8}, # 更淡的颜色和样式
            'buy_grid_2': {'color': 'lightgreen', 'linestyle': ':', 'linewidth': 0.8},
        },
        'subplots': {
            "ATR": {
                'atr': {'color': 'blue'}
            },
            "Step": {
                 'dynamic_step_pct': {'color': 'purple'} # 绘制步长百分比
            }
        }
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算指标和动态网格线
        """
        # 1. 网格中心线 (EMA)
        dataframe['ema_center'] = ta.EMA(dataframe, timeperiod=self.grid_center_ema_period.value)

        # 2. ATR 用于动态步长
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.grid_atr_period.value)

        # 3. 动态网格步长 (基于中心价格的百分比)
        # 防止除以零或NaN
        dataframe['dynamic_step_pct'] = (dataframe['atr'] / dataframe['ema_center'].replace(0, np.nan)) * self.grid_step_multiplier.value
        dataframe['dynamic_step_pct'].fillna(method='ffill', inplace=True) # 向前填充NaN

        # 4. 计算并添加网格线到 DataFrame
        for i in range(1, self.grid_levels.value + 1):
            step_factor = i * dataframe['dynamic_step_pct']
            # 卖出网格线 (高于中心线)
            dataframe[f'sell_grid_{i}'] = dataframe['ema_center'] * (1 + step_factor)
            # 买入网格线 (低于中心线)
            dataframe[f'buy_grid_{i}'] = dataframe['ema_center'] * (1 - step_factor)

            # --- 添加用于绘图配置的检查 ---
            # 确保即使 grid_levels=1 也能绘制 sell_grid_2 等 (用NaN填充)
            # Freqtrade 绘图时会忽略不存在的列，但这样做更明确
            if i >= 2 and f'sell_grid_{i}' not in self.plot_config['main_plot']:
                 if i > self.grid_levels.value: # 如果循环次数少于配置的绘图层级
                    if f'sell_grid_{i}' in self.plot_config['main_plot']:
                        dataframe[f'sell_grid_{i}'] = np.nan
                    if f'buy_grid_{i}' in self.plot_config['main_plot']:
                        dataframe[f'buy_grid_{i}'] = np.nan


        # print(dataframe[['date', 'close', 'ema_center', 'atr', 'dynamic_step_pct', 'sell_grid_1', 'buy_grid_1']].tail()) # 调试用
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义入场信号: 当价格向下穿越任何一条买入网格线
        """
        conditions = []
        # 检查是否向下穿越了任何一条买入网格线
        for i in range(1, self.grid_levels.value + 1):
            conditions.append(
                qtpylib.crossed_below(dataframe['close'], dataframe[f'buy_grid_{i}'])
            )

        # 合并所有买入条件: 如果任一条件为 True
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions), # 使用 reduce 和 | (OR) 合并条件
                'enter_long'] = 1
            # 可选: 设置自定义入场价格 (例如，触发的网格线价格)
            # dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = f'crossed_buy_grid' # 添加标签

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义出场信号: 当价格向上穿越任何一条卖出网格线
        """
        conditions = []
        # 检查是否向上穿越了任何一条卖出网格线
        for i in range(1, self.grid_levels.value + 1):
            conditions.append(
                qtpylib.crossed_above(dataframe['close'], dataframe[f'sell_grid_{i}'])
            )

        # 合并所有卖出条件: 如果任一条件为 True
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, conditions), # 使用 reduce 和 | (OR) 合并条件
                'exit_long'] = 1
            # 可选: 添加标签
            # dataframe.loc[dataframe['exit_long'] == 1, 'exit_tag'] = f'crossed_sell_grid'

        return dataframe

