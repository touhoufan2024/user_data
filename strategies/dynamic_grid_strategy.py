from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from technical.indicators import ema, sma, atr
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, CategoricalParameter

class DynamicGridWeightStrategy(IStrategy):
    """
    基于动态网格的交易策略，每个网格仅触发一次信号，带权重仓位分配。
    支持 Freqtrade 的超参数优化。
    """

    # 配置策略参数
    minimal_roi = {"0": 0.02}  # 固定收益
    stoploss = -0.1           # 最大止损 10%
    timeframe = '1h'          # 时间周期为 1 小时

    # 定义超参数范围（供 Hyperopt 优化使用）
    grid_size = IntParameter(3, 10, default=5, space="buy", optimize=True)  # 网格数量（上下各 3~10 个）
    atr_multiplier = DecimalParameter(0.5, 3.0, default=1.5, space="buy", optimize=True)  # ATR 倍数
    ma_type = CategoricalParameter(["ema", "sma"], default="ema", space="buy", optimize=True)  # 均线类型
    ma_period = IntParameter(20, 100, default=50, space="buy", optimize=True)  # 均线周期
    weight_mode = CategoricalParameter(["linear", "exponential"], default="linear", space="buy", optimize=True)  # 权重模式

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所需指标：移动均线、ATR，以及动态网格。
        """
        # 选择移动均线类型
        if self.ma_type.value == "ema":
            dataframe["mid_line"] = ema(dataframe["close"], self.ma_period.value)
        else:
            dataframe["mid_line"] = sma(dataframe["close"], self.ma_period.value)

        # 计算 ATR，作为动态间距的基础
        dataframe["atr"] = atr(dataframe, 14)

        # 生成上下网格
        for i in range(1, self.grid_size.value + 1):
            dataframe[f"grid_upper_{i}"] = dataframe["mid_line"] + i * self.atr_multiplier.value * dataframe["atr"]
            dataframe[f"grid_lower_{i}"] = dataframe["mid_line"] - i * self.atr_multiplier.value * dataframe["atr"]

            # 初始化触发状态为 False
            dataframe[f"triggered_upper_{i}"] = False
            dataframe[f"triggered_lower_{i}"] = False

            # 计算网格权重
            if self.weight_mode.value == "linear":
                # 线性权重分配
                dataframe[f"grid_weight_{i}"] = i
            elif self.weight_mode.value == "exponential":
                # 指数权重分配
                dataframe[f"grid_weight_{i}"] = 2 ** i

        return dataframe

    def reset_trigger_status(self, dataframe: DataFrame) -> DataFrame:
        """
        重置网格触发状态，当价格远离网格时。
        """
        # 如果价格超过最高的上网格，重置所有上网格状态
        all_upper_triggered = (
            dataframe['close'] > dataframe[f'grid_upper_{self.grid_size.value}']
        )
        for i in range(1, self.grid_size.value + 1):
            dataframe.loc[all_upper_triggered, f'triggered_upper_{i}'] = False

        # 如果价格低于最低的下网格，重置所有下网格状态
        all_lower_triggered = (
            dataframe['close'] < dataframe[f'grid_lower_{self.grid_size.value}']
        )
        for i in range(1, self.grid_size.value + 1):
            dataframe.loc[all_lower_triggered, f'triggered_lower_{i}'] = False

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        开仓逻辑：每个网格只触发一次，并基于权重进行仓位分配。
        """
        # 先重置触发状态
        dataframe = self.reset_trigger_status(dataframe)

        # 初始化信号
        dataframe['enter_long'] = False
        dataframe['enter_short'] = False
        dataframe['position_size'] = 0  # 初始化仓位大小为 0

        for i in range(1, self.grid_size.value + 1):
            # 检查下网格（开多信号）
            cond_long = (
                (dataframe['close'] <= dataframe[f'grid_lower_{i}']) &  # 当前价格小于等于下网格
                (~dataframe[f'triggered_lower_{i}'])                   # 并且网格未触发过
            )
            dataframe[f'long_grid_{i}'] = cond_long
            dataframe['enter_long'] |= cond_long
            dataframe.loc[cond_long, f'triggered_lower_{i}'] = True  # 标记网格已触发

            # 权重对应仓位
            dataframe.loc[cond_long, "position_size"] = dataframe[f"grid_weight_{i}"]

            # 检查上网格（开空信号）
            cond_short = (
                (dataframe['close'] >= dataframe[f'grid_upper_{i}']) &  # 当前价格大于等于上网格
                (~dataframe[f'triggered_upper_{i}'])                   # 并且网格未触发过
            )
            dataframe[f'short_grid_{i}'] = cond_short
            dataframe['enter_short'] |= cond_short
            dataframe.loc[cond_short, f'triggered_upper_{i}'] = True  # 标记网格已触发

            # 权重对应仓位
            dataframe.loc[cond_short, "position_size"] = dataframe[f"grid_weight_{i}"]

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        平仓逻辑：在网格触发信号的另一侧平仓。
        """
        dataframe['exit_long'] = False
        dataframe['exit_short'] = False

        # 检查平多信号（价格触碰上网格）
        for i in range(1, self.grid_size.value + 1):
            cond_exit_long = (dataframe['close'] >= dataframe[f'grid_upper_{i}'])
            dataframe['exit_long'] |= cond_exit_long

        # 检查平空信号（价格触碰下网格）
        for i in range(1, self.grid_size.value + 1):
            cond_exit_short = (dataframe['close'] <= dataframe[f'grid_lower_{i}'])
            dataframe['exit_short'] |= cond_exit_short

        return dataframe
