from freqtrade.strategy import IStrategy
from pandas_ta import rsi
import logging
from freqtrade.persistence import Trade
from pandas import DataFrame

logger = logging.getLogger(__name__)

class SimpleRSIStrategy(IStrategy):
    # 策略参数
    INTERFACE_VERSION = 3
    
    position_adjustment_enable = True  # 启用仓位调整
    # 买入参数
    buy_rsi = 30
    # 卖出参数
    sell_rsi = 70
    
    # 止损
    stoploss = -0.1
    
    # 时间框架
    timeframe = '5m'
    
    # 最小回测天数
    minimal_roi = {
        "0": 0.1
    }
    
    # 指标计算
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = rsi(dataframe['close'], length=14)
        return dataframe
    
    # 买入信号
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] < self.buy_rsi),
            'enter_long'] = 1
        return dataframe
    
    # 卖出信号
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] > self.sell_rsi),
            'exit_long'] = 1
        return dataframe
    
    # 仓位调整逻辑
    def adjust_trade_position(self, trade: Trade, current_time, current_rate: float,
                            current_profit: float, min_stake: float, max_stake: float,
                            current_entry_rate: float, current_exit_rate: float,
                            current_profit_ratio: float, **kwargs):
        """
        仓位调整逻辑：
        1. 盈利超过5%时减仓50%
        2. 价格下跌5%时加仓一倍
        """
        try:
            # 获取当前交易对的最新数据
            df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            last_candle = df.iloc[-1].squeeze()
            
            # 减仓逻辑：当盈利超过5%时，减仓50%
            if current_profit_ratio > 0.05:
                logger.info(f"Reducing position for {trade.pair}, current profit: {current_profit_ratio:.2%}")
                return -trade.amount * 0.5  # 负数表示减少仓位
            
            # 加仓逻辑：当价格下跌5%时，加仓一倍
            price_drop = (trade.open_rate - current_rate) / trade.open_rate
            if price_drop > 0.05 and trade.stake_amount * 2 <= max_stake:
                logger.info(f"Adding to position for {trade.pair}, price drop: {price_drop:.2%}")
                return trade.stake_amount  # 正数表示增加仓位
            
            return None  # 不调整仓位
            
        except Exception as e:
            logger.error(f"Error in adjust_trade_position: {str(e)}")
            return None