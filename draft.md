# start
source ./.venv/bin/activate



# 显示当前

策略





绘制彩虹图

新建了一个默认策略, 看看它默认是 干什么的




默认 只有三个函数,  指标计算, 入场策略和出场策略



首先把 彩虹图的 几条线 先看一下
彩虹图 指标





upline = low + x * ma(ta.tr)


mid = ma(hcl3, len)


downline = high - x * ma(ta.tr)


不支持 vwma, 所以暂时用sma 代替


定义了几个参数 文件
如果 不设置的 话  应该会使用 默认的参数 文件



hcl3 = (最高价+最低价+收盘价)/3



ta.tr

真实范围，相当于ta.tr(handle_na = false)。其计算方式为math.max(high - low, math.abs(high - close[1]), math.abs(low - close[1]))。


x1 = input.float(10, '1', minval=-3000, maxval=3000, group = "系数设置")
x2 = input.float(7.3, '2', minval=-3000, maxval=3000, group = "系数设置")
x3 = input.float(5, '3', minval=-3000, maxval=3000, group = "系数设置")
x4 = input.float(3.65, '4', minval=-3000, maxval=3000, group = "系数设置")
x6 = input.float(-3.65, '6', minval=-3000, maxval=3000, group = "系数设置")
x7 = input.float(-5, '7', minval=-3000, maxval=3000, group = "系数设置")
x8 = input.float(-7.3, '8', minval=-3000, maxval=3000, group = "系数设置")
x9 = input.float(-10, '9', minval=-3000, maxval=3000, group = "系数设置")



upline = ma(low) + x * ma(ta.tr)


mid = ma(hlc3, len)


downline = ma(high) - x * ma(ta.tr)


需要做的事情

实现 vwma   使用 wma
彩虹鹅 进出场 


回测

研究 超参数优化 和 ai


空单进场
high 上穿 1 2 3 4

空单出场 止盈


多单进场 

low  下穿 6 7 8 9



https://www.freqtrade.io/en/stable/strategy-advanced/#exit-tag




def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[
        (
            (dataframe['rsi'] > 70) &
            (dataframe['volume'] > 0)
        ),
        ['exit_long', 'exit_tag']] = (1, 'exit_rsi')

    return dataframe


def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[
        (
            (dataframe['rsi'] < 35) &
            (dataframe['volume'] > 0)
        ),
        ['enter_long', 'enter_tag']] = (1, 'buy_signal_rsi')

    return dataframe

def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                current_profit: float, **kwargs):
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    last_candle = dataframe.iloc[-1].squeeze()
    if trade.enter_tag == 'buy_signal_rsi' and last_candle['rsi'] > 80:
        return 'sell_signal_rsi'
    return None



还是得先看一下 别人 写的 代码 是怎么 样子的


做个简单版本的, 1线开空, 9线做多

进行回测

freqtrade test-pairlist

freqtrade backtesting --config user_data/config.json --strategy SampleStrategy --timeframe 5m --timerange=20240101-  -p BTC/USDT:USDT




配置参数的 优先级如下
命令行输入参数
环境变量
config文件, 排在后面的 文件优先级更高, 会覆盖前面的
strategy里配置的 参数















