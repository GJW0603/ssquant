import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union


def _period_to_timedelta(period_str: str) -> pd.Timedelta:
    """将K线周期字符串转为 pd.Timedelta，支持任意数字前缀。
    
    支持格式: 1m/3m/65m/120m, 1h/2h/4h, 1d/2d/d, 1w/2w/w 等
    """
    p = period_str.lower().strip()
    m = re.match(r'^(\d+)(m|min)$', p)
    if m:
        return pd.Timedelta(minutes=int(m.group(1)))
    m = re.match(r'^(\d+)(h|hour)$', p)
    if m:
        return pd.Timedelta(hours=int(m.group(1)))
    m = re.match(r'^(\d+)(d|day)$', p)
    if m:
        return pd.Timedelta(days=int(m.group(1)))
    if p in ('d', 'day'):
        return pd.Timedelta(days=1)
    m = re.match(r'^(\d+)(w|week)$', p)
    if m:
        return pd.Timedelta(weeks=int(m.group(1)))
    if p in ('w', 'week'):
        return pd.Timedelta(weeks=1)
    print(f"[警告] 无法识别的K线周期 '{period_str}'，默认按1分钟处理")
    return pd.Timedelta(minutes=1)


class DataSource:
    """
    数据源类，用于管理单个数据源的数据和交易操作
    """
    
    def __init__(self, symbol: str, kline_period: str, adjust_type: str = '1', lookback_bars: int = 0,
                 slippage_ticks: int = 1, price_tick: float = 1.0):
        """
        初始化数据源
        
        Args:
            symbol: 品种代码，如'rb888'
            kline_period: K线周期，如'1h', 'D'
            adjust_type: 复权类型，'0'表示不复权，'1'表示后复权
            lookback_bars: K线回溯窗口大小，0表示不限制（返回全部历史数据）
            slippage_ticks: 滑点跳数，默认1跳
            price_tick: 最小变动价位，默认1.0
        """
        self.symbol = symbol
        self.kline_period = kline_period
        self.adjust_type = adjust_type
        self.lookback_bars = lookback_bars  # K线回溯窗口大小
        self.slippage_ticks = slippage_ticks  # 滑点跳数
        self.price_tick = price_tick  # 最小变动价位
        self.data = pd.DataFrame()
        self.current_pos = 0
        self.target_pos = 0
        self.signal_reason = ""
        self.trades = []
        self.current_idx = 0
        self.current_price = None
        self.current_datetime = None
        self.pending_orders = []  # 存储待执行的订单
        self.original_data = None
        self._is_higher_tf = False
        self.symbol_config = {}
        self.account_info = None
        self.account_sync_callback = None

    def configure_backtest_context(self, symbol_config: Optional[Dict[str, Any]] = None,
                                   account_info: Optional[Dict[str, Any]] = None,
                                   account_sync_callback=None):
        """绑定回测账户上下文，用于资金校验与实时账户同步。"""
        self.symbol_config = (symbol_config or {}).copy()
        self.account_info = account_info
        self.account_sync_callback = account_sync_callback

    def _sync_backtest_account(self):
        """同步回测账户快照，保证同一根K线内的后续下单也能看到最新资金。"""
        if callable(self.account_sync_callback):
            self.account_sync_callback()

    def _get_open_cost_per_lot(self, price: Optional[float]) -> float:
        """估算开仓每手占用资金（保证金+开仓手续费）。"""
        if price is None or price <= 0:
            return 0.0

        margin_required = self._get_margin_required(price, 1)
        open_commission = self._get_trade_commission("开多", price, 1)
        return margin_required + open_commission

    def _use_fixed_commission(self) -> bool:
        commission_rate = float(self.symbol_config.get('commission', 0.0003) or 0.0)
        commission_per_lot = float(self.symbol_config.get('commission_per_lot', 0) or 0.0)
        return commission_rate < 1e-05 and commission_per_lot > 0.1

    def _get_margin_required(self, price: Optional[float], volume: int) -> float:
        if price is None or price <= 0 or volume <= 0:
            return 0.0
        contract_multiplier = float(self.symbol_config.get('contract_multiplier', 10) or 10)
        margin_rate = float(self.symbol_config.get('margin_rate', 0.1) or 0.1)
        return float(price) * int(volume) * contract_multiplier * margin_rate

    def _get_trade_commission(self, action: str, price: Optional[float], volume: int) -> float:
        if price is None or price <= 0 or volume <= 0:
            return 0.0

        volume = int(volume)
        contract_multiplier = float(self.symbol_config.get('contract_multiplier', 10) or 10)
        commission_rate = float(self.symbol_config.get('commission', 0.0003) or 0.0)
        commission_per_lot = float(self.symbol_config.get('commission_per_lot', 0) or 0.0)
        commission_close_per_lot = float(self.symbol_config.get('commission_close_per_lot', 0) or 0.0)

        if self._use_fixed_commission():
            if action in ("平多", "平空"):
                fixed_per_lot = commission_close_per_lot if commission_close_per_lot > 0 else commission_per_lot
            else:
                fixed_per_lot = commission_per_lot
            return fixed_per_lot * volume

        return float(price) * volume * contract_multiplier * commission_rate

    def get_runtime_account_snapshot(self, current_price: Optional[float] = None) -> Dict[str, float]:
        """根据运行中的成交记录重建该数据源的账户快照。"""
        contract_multiplier = float(self.symbol_config.get('contract_multiplier', 10) or 10)
        margin_rate = float(self.symbol_config.get('margin_rate', 0.1) or 0.1)
        current_price = float(current_price or self.current_price or 0.0)

        long_pos = 0
        long_avg_price = 0.0
        short_pos = 0
        short_avg_price = 0.0
        close_profit = 0.0
        total_commission = 0.0

        def open_long(price: float, volume: int):
            nonlocal long_pos, long_avg_price, total_commission
            total_commission += self._get_trade_commission("开多", price, volume)
            if long_pos > 0:
                long_avg_price = (long_pos * long_avg_price + volume * price) / (long_pos + volume)
            else:
                long_avg_price = price
            long_pos += volume

        def close_long(price: float, volume: int) -> int:
            nonlocal long_pos, long_avg_price, close_profit, total_commission
            actual_volume = min(volume, long_pos)
            if actual_volume <= 0:
                return 0
            total_commission += self._get_trade_commission("平多", price, actual_volume)
            close_profit += (price - long_avg_price) * actual_volume * contract_multiplier
            long_pos -= actual_volume
            if long_pos <= 0:
                long_pos = 0
                long_avg_price = 0.0
            return actual_volume

        def open_short(price: float, volume: int):
            nonlocal short_pos, short_avg_price, total_commission
            total_commission += self._get_trade_commission("开空", price, volume)
            if short_pos > 0:
                short_avg_price = (short_pos * short_avg_price + volume * price) / (short_pos + volume)
            else:
                short_avg_price = price
            short_pos += volume

        def close_short(price: float, volume: int) -> int:
            nonlocal short_pos, short_avg_price, close_profit, total_commission
            actual_volume = min(volume, short_pos)
            if actual_volume <= 0:
                return 0
            total_commission += self._get_trade_commission("平空", price, actual_volume)
            close_profit += (short_avg_price - price) * actual_volume * contract_multiplier
            short_pos -= actual_volume
            if short_pos <= 0:
                short_pos = 0
                short_avg_price = 0.0
            return actual_volume

        for trade in self.trades:
            action = trade.get('action')
            price = float(trade.get('price', 0) or 0.0)
            volume = int(trade.get('volume', 0) or 0)
            if price <= 0 or volume <= 0:
                continue

            if action == "开多":
                open_long(price, volume)
            elif action == "平多":
                close_long(price, volume)
            elif action == "开空":
                open_short(price, volume)
            elif action == "平空":
                close_short(price, volume)
            elif action == "平多开空":
                reversed_volume = close_long(price, volume)
                if reversed_volume > 0:
                    open_short(price, reversed_volume)
            elif action == "平空开多":
                reversed_volume = close_short(price, volume)
                if reversed_volume > 0:
                    open_long(price, reversed_volume)

        long_position_profit = (current_price - long_avg_price) * long_pos * contract_multiplier if long_pos > 0 else 0.0
        short_position_profit = (short_avg_price - current_price) * short_pos * contract_multiplier if short_pos > 0 else 0.0
        position_profit = long_position_profit + short_position_profit
        curr_margin = (long_pos + short_pos) * current_price * contract_multiplier * margin_rate

        return {
            'close_profit': close_profit,
            'commission': total_commission,
            'position_profit': position_profit,
            'curr_margin': curr_margin,
        }

    def _fit_open_volume_to_funds(self, requested_volume: int, price: Optional[float],
                                  extra_reserved_funds: float = 0.0):
        """
        根据当前可用资金裁剪开仓手数。

        返回:
            (actual_volume, reserved_funds)
        """
        requested_volume = int(requested_volume or 0)
        if requested_volume <= 0:
            return 0, 0.0

        cost_per_lot = self._get_open_cost_per_lot(price)
        if cost_per_lot <= 0:
            return requested_volume, 0.0

        if self.account_info is None:
            return requested_volume, cost_per_lot * requested_volume

        available = float(self.account_info.get('available', 0) or 0.0) + max(0.0, float(extra_reserved_funds or 0.0))
        max_volume = int(np.floor(available / cost_per_lot)) if cost_per_lot > 0 else requested_volume
        actual_volume = max(0, min(requested_volume, max_volume))
        reserved_funds = cost_per_lot * actual_volume
        return actual_volume, reserved_funds

    def _mark_insufficient_funds(self, message: str = ""):
        if self.account_info is not None:
            self.account_info['_last_order_rejected_for_funds'] = True
            self.account_info['_fund_reject_count'] = int(self.account_info.get('_fund_reject_count', 0) or 0) + 1
            if message:
                self.account_info['_last_fund_reject_reason'] = message
        
    def set_data(self, data: pd.DataFrame):
        """设置数据"""
        self.data = data
        
    def get_data(self) -> pd.DataFrame:
        """获取数据"""
        return self.data
        
    def get_current_price(self) -> Optional[float]:
        """获取当前价格"""
        if self.current_price is not None:
            return self.current_price
        if not self.data.empty and self.current_idx < len(self.data):
            return self.data.iloc[self.current_idx]['close']
        return None
        
    def get_current_datetime(self):
        """获取当前日期时间"""
        if self.current_datetime is not None:
            return self.current_datetime
        if not self.data.empty and self.current_idx < len(self.data):
            return self.data.index[self.current_idx]
        return None
        
    def get_current_pos(self) -> int:
        """获取当前持仓"""
        return self.current_pos
        
    def _update_pos(self, log_callback=None):
        """更新实际持仓"""
        if self.current_pos != self.target_pos:
            old_pos = self.current_pos
            self.current_pos = self.target_pos
            if log_callback:
                # 添加debug参数检查
                debug_mode = getattr(log_callback, 'debug_mode', True)
                if debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 持仓变化: {old_pos} -> {self.current_pos}")
                
    def set_target_pos(self, target_pos: int, log_callback=None):
        """设置目标持仓"""
        self.target_pos = target_pos
        self._update_pos(log_callback)
        
    def set_signal_reason(self, reason: str):
        """设置交易信号原因"""
        self.signal_reason = reason
        
    def add_trade(self, action: str, price: float, volume: int, reason: str, datetime=None, slippage_cost: float = 0):
        """添加交易记录
        
        Args:
            action: 交易动作
            price: 成交价格（已含滑点）
            volume: 交易数量
            reason: 交易原因
            datetime: 交易时间
            slippage_cost: 滑点成本（元）
        """
        if datetime is None:
            datetime = self.get_current_datetime()
        
        self.trades.append({
            'datetime': datetime,
            'action': action,
            'price': price,
            'volume': volume,
            'reason': '',  # 不再记录原因
            'slippage_cost': slippage_cost  # 滑点成本
        })
        
    def get_price_by_type(self, order_type='bar_close'):
        """
        根据订单类型获取价格
        
        Args:
            order_type (str): 订单类型，可选值：
                - 'bar_close': 当前K线收盘价（默认）
                - 'next_bar_open': 下一K线开盘价
                - 'next_bar_close': 下一K线收盘价
                - 'next_bar_high': 下一K线最高价
                - 'next_bar_low': 下一K线最低价
                - 'market': 市价单，按对手价成交，买入按ask1，卖出按bid1
        
        Returns:
            float: 价格，如果无法获取则返回None
        """
        if not self.data.empty:
            if order_type == 'bar_close':
                if self.current_idx < len(self.data):
                    return self.data.iloc[self.current_idx]['close']
            elif order_type == 'next_bar_open':
                if self.current_idx + 1 < len(self.data) and 'open' in self.data.columns:
                    return self.data.iloc[self.current_idx + 1]['open']
            elif order_type == 'next_bar_close':
                if self.current_idx + 1 < len(self.data):
                    return self.data.iloc[self.current_idx + 1]['close']
            elif order_type == 'next_bar_high':
                if self.current_idx + 1 < len(self.data) and 'high' in self.data.columns:
                    return self.data.iloc[self.current_idx + 1]['high']
            elif order_type == 'next_bar_low':
                if self.current_idx + 1 < len(self.data) and 'low' in self.data.columns:
                    return self.data.iloc[self.current_idx + 1]['low']
            elif order_type == 'market':
                # 市价单，对于tick数据，可以使用买一卖一价格
                if self.current_idx < len(self.data):
                    if 'BidPrice1' in self.data.columns and 'AskPrice1' in self.data.columns:
                        # TICK数据：在具体的buy/sell方法中根据买卖方向确定价格
                        return None
                    else:
                        # K线数据：使用收盘价
                        return self.data.iloc[self.current_idx]['close']
        return None
        
    def _process_pending_orders(self, log_callback=None):
        """处理待执行的订单"""
        if not self.pending_orders:
            return
        
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        orders_to_remove = []
        for i, order in enumerate(self.pending_orders):
            # 获取执行时间
            execution_time = order.get('execution_time', self.current_idx + 1)
            
            # 获取订单类型（默认为next_bar_open）
            order_type = order.get('order_type', 'next_bar_open')
            
            # 判断是否到达执行时间
            if execution_time <= self.current_idx:
                # 执行订单
                action = order['action']
                volume = order['volume']
                reason = order['reason']
                
                # 根据订单类型获取执行价格
                # 如果已经预先计算了价格，就使用那个价格
                if 'price' in order and order['price'] is not None:
                    price = order['price']
                else:
                    # 否则根据订单类型获取当前价格
                    price = self.get_price_by_type(order_type)
                    if price is None:
                        # 如果仍然无法获取价格，则使用当前价格
                        price = self.get_current_price()
                        if price is None:
                            # 如果完全无法获取价格，跳过此订单
                            continue
                
                # 应用滑点成本（买入加滑点，卖出减滑点）
                slippage_per_unit = self.slippage_ticks * self.price_tick  # 每单位滑点金额
                if action in ["开多", "平空", "平空开多"]:
                    # 买入方向：价格上滑
                    price = price + slippage_per_unit
                elif action in ["开空", "平多", "平多开空"]:
                    # 卖出方向：价格下滑
                    price = price - slippage_per_unit

                if action in ["开多", "开空"]:
                    reserved_funds = float(order.get('reserved_funds', 0.0) or 0.0)
                    actual_volume, actual_reserved = self._fit_open_volume_to_funds(
                        volume, price, extra_reserved_funds=reserved_funds
                    )
                    if actual_volume <= 0:
                        if log_callback:
                            log_callback(
                                f"{self.symbol} {self.kline_period} 取消待执行开仓订单: "
                                f"资金不足，请求{volume}手，执行价{price:.2f}"
                            )
                        self._mark_insufficient_funds(
                            f"{self.symbol} {self.kline_period} 待执行开仓被取消：资金不足，请求{volume}手，执行价{price:.2f}"
                        )
                        order['reserved_funds'] = 0.0
                        orders_to_remove.append(i)
                        self._sync_backtest_account()
                        continue
                    if actual_volume < volume and log_callback:
                        log_callback(
                            f"{self.symbol} {self.kline_period} 待执行开仓资金不足: "
                            f"{volume}手自动调整为{actual_volume}手"
                        )
                    volume = actual_volume
                
                # 更新持仓
                if action == "开多":
                    self.target_pos = self.current_pos + volume
                elif action == "平多":
                    if volume is None:
                        volume = max(0, self.current_pos)
                    # 检查是否有多头持仓可平
                    actual_volume = min(volume, max(0, self.current_pos))
                    if actual_volume <= 0:
                        # 没有多头持仓可平，跳过此订单
                        orders_to_remove.append(i)
                        self._sync_backtest_account()
                        continue
                    self.target_pos = self.current_pos - actual_volume
                    volume = actual_volume  # 更新volume为实际交易量
                elif action == "开空":
                    self.target_pos = self.current_pos - volume
                elif action == "平空":
                    if volume is None:
                        volume = max(0, -self.current_pos)
                    # 检查是否有空头持仓可平
                    actual_volume = min(volume, max(0, -self.current_pos))
                    if actual_volume <= 0:
                        # 没有空头持仓可平，跳过此订单
                        orders_to_remove.append(i)
                        self._sync_backtest_account()
                        continue
                    self.target_pos = self.current_pos + actual_volume
                    volume = actual_volume  # 更新volume为实际交易量
                elif action == "平多开空":  # 支持反手交易
                    self.target_pos = -self.current_pos  # 从多头变为空头
                elif action == "平空开多":  # 支持反手交易
                    self.target_pos = -self.current_pos  # 从空头变为多头
                
                # 更新持仓
                self._update_pos(log_callback)
                
                # 记录交易（包含单位滑点金额，用于后续计算滑点成本）
                self.add_trade(action, price, volume, reason, slippage_cost=slippage_per_unit)
                
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 执行订单: {action} {volume}手 成交价:{price:.2f} 类型:{order_type} 原因:{reason}")
                
                # 标记为待移除
                order['reserved_funds'] = 0.0
                orders_to_remove.append(i)
                self._sync_backtest_account()
        
        # 移除已执行的订单（从后往前移除，避免索引问题）
        for i in sorted(orders_to_remove, reverse=True):
            self.pending_orders.pop(i)

        if orders_to_remove:
            self._sync_backtest_account()
        
    def buy(self, volume: int = 1, reason: str = "", log_callback=None, order_type='bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """
        开多仓
        
        Args:
            volume (int): 交易数量
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值：
                - 'limit': 限价单（需指定price）
                - 'bar_close': 当前K线收盘价（默认）
                - 'next_bar_open': 下一K线开盘价
                - 'next_bar_close': 下一K线收盘价
                - 'next_bar_high': 下一K线最高价
                - 'next_bar_low': 下一K线最低价
                - 'market': 市价单，按ask1价格成交（买入用卖一价）
            offset_ticks: 价格偏移tick数
            price: 限价单价格（仅当order_type='limit'时有效）
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        if order_type == 'bar_close':
            # 当前K线收盘价下单，立即执行
            price = self.get_current_price()
            if price is None:
                return False

            actual_volume, _ = self._fit_open_volume_to_funds(volume, price)
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 开多失败: 资金不足，请求{volume}手 成交价:{price:.2f}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 开多失败：资金不足，请求{volume}手，参考价{price:.2f}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 开多资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
                
            self.target_pos = self.current_pos + volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("开多", price, volume, reason)
            self._sync_backtest_account()
            return True
        elif order_type == 'market':
            # 市价单，TICK数据买入使用卖一价格(AskPrice1)
            price = None
            if 'AskPrice1' in self.data.columns and self.current_idx < len(self.data):
                price = self.data.iloc[self.current_idx]['AskPrice1']
            else:
                price = self.get_current_price()
            
            if price is None:
                return False

            actual_volume, _ = self._fit_open_volume_to_funds(volume, price)
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 市价买入失败: 资金不足，请求{volume}手 成交价:{price:.2f}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 市价买入失败：资金不足，请求{volume}手，参考价{price:.2f}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价买入资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
                
            self.target_pos = self.current_pos + volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("开多", price, volume, reason)
            
            if log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价买入: {volume}手 成交价:{price:.2f} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        else:
            # 下一K线价格下单，添加到待执行队列
            if price is None:
                price = self.get_price_by_type(order_type)
            estimate_price = price if price is not None else self.get_current_price()
            actual_volume, reserved_funds = self._fit_open_volume_to_funds(volume, estimate_price)
            price_str = f"{estimate_price:.2f}" if estimate_price is not None else "未知"
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 开多订单失败: 资金不足，请求{volume}手 参考价:{price_str}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 开多订单失败：资金不足，请求{volume}手，参考价{price_str}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 开多订单资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
            
            # 注意：如果是next_bar_open/high/low/close，价格可能为None，因为下一K线的数据尚未加载
            # 但我们仍然可以添加到待执行队列，等待下一K线时执行，再根据order_type获取正确的价格
            
            # 添加到待执行队列
            self.pending_orders.append({
                'action': "开多",
                'volume': volume,
                'price': price,  # 可能为None，将在执行时重新获取
                'reason': reason,
                'order_type': order_type,  # 保存订单类型
                'execution_time': self.current_idx + 1,  # 在下一K线执行
                'reserved_funds': reserved_funds,
            })
            
            if log_callback and debug_mode:
                price_str = f"{price:.2f}" if price is not None else "待确定"
                log_callback(f"{self.symbol} {self.kline_period} 添加待执行订单: 开多 {volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        
    def sell(self, volume: Optional[int] = None, reason: str = "", log_callback=None, order_type='bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """
        平多仓
        
        Args:
            volume (int, optional): 交易数量，None表示平掉所有多仓
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值同buy函数
            offset_ticks: 价格偏移tick数
            price: 限价单价格（仅当order_type='limit'时有效）
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        if order_type == 'bar_close':
            # 当前K线收盘价下单，立即执行
            price = self.get_current_price()
            if price is None:
                return False
                
            if volume is None:
                volume = max(0, self.current_pos)
            
            # 检查是否有多头持仓可平
            actual_volume = min(volume, max(0, self.current_pos))
            if actual_volume <= 0:
                # 没有多头持仓可平，不记录交易
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 平多失败: 无多头持仓可平")
                return True
                
            self.target_pos = self.current_pos - actual_volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("平多", price, actual_volume, reason)
            self._sync_backtest_account()
            return True
        elif order_type == 'market':
            # 市价单，TICK数据卖出使用买一价格(BidPrice1)
            price = None
            if 'BidPrice1' in self.data.columns and self.current_idx < len(self.data):
                price = self.data.iloc[self.current_idx]['BidPrice1']
            else:
                price = self.get_current_price()
            
            if price is None:
                return False
                
            if volume is None:
                volume = max(0, self.current_pos)
            
            # 检查是否有多头持仓可平
            actual_volume = min(volume, max(0, self.current_pos))
            if actual_volume <= 0:
                # 没有多头持仓可平，不记录交易
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 市价平多失败: 无多头持仓可平")
                return True
                
            self.target_pos = self.current_pos - actual_volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("平多", price, actual_volume, reason)
            
            if log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价卖出: {actual_volume}手 成交价:{price:.2f} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        else:
            # 下一K线价格下单，添加到待执行队列
            if price is None:
                price = self.get_price_by_type(order_type)
            # 注意：如果是next_bar_open/high/low/close，价格可能为None，因为下一K线的数据尚未加载
            
            if volume is None:
                volume = max(0, self.current_pos)
            
            # 检查是否有多头持仓可平
            actual_volume = min(volume, max(0, self.current_pos))
            if actual_volume <= 0:
                # 没有多头持仓可平，不添加订单
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 平多订单失败: 无多头持仓可平")
                return True
            
            # 添加到待执行队列
            self.pending_orders.append({
                'action': "平多",
                'volume': actual_volume,
                'price': price,  # 可能为None，将在执行时重新获取
                'reason': reason,
                'order_type': order_type,  # 保存订单类型
                'execution_time': self.current_idx + 1  # 在下一K线执行
            })
            
            if log_callback and debug_mode:
                price_str = f"{price:.2f}" if price is not None else "待确定"
                log_callback(f"{self.symbol} {self.kline_period} 添加待执行订单: 平多 {actual_volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
            
            return True
        
    def sellshort(self, volume: int = 1, reason: str = "", log_callback=None, order_type='bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """
        开空仓
        
        Args:
            volume (int): 交易数量
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值同buy函数
            offset_ticks: 价格偏移tick数
            price: 限价单价格（仅当order_type='limit'时有效）
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        if order_type == 'bar_close':
            # 当前K线收盘价下单，立即执行
            price = self.get_current_price()
            if price is None:
                return False

            actual_volume, _ = self._fit_open_volume_to_funds(volume, price)
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 开空失败: 资金不足，请求{volume}手 成交价:{price:.2f}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 开空失败：资金不足，请求{volume}手，参考价{price:.2f}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 开空资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
                
            self.target_pos = self.current_pos - volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("开空", price, volume, reason)
            self._sync_backtest_account()
            return True
        elif order_type == 'market':
            # 市价单，TICK数据卖出使用买一价格(BidPrice1)
            price = None
            if 'BidPrice1' in self.data.columns and self.current_idx < len(self.data):
                price = self.data.iloc[self.current_idx]['BidPrice1']
            else:
                price = self.get_current_price()
            
            if price is None:
                return False

            actual_volume, _ = self._fit_open_volume_to_funds(volume, price)
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 市价卖空失败: 资金不足，请求{volume}手 成交价:{price:.2f}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 市价卖空失败：资金不足，请求{volume}手，参考价{price:.2f}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价卖空资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
                
            self.target_pos = self.current_pos - volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("开空", price, volume, reason)
            
            if log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价卖空: {volume}手 成交价:{price:.2f} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        else:
            # 下一K线价格下单，添加到待执行队列
            if price is None:
                price = self.get_price_by_type(order_type)
            estimate_price = price if price is not None else self.get_current_price()
            actual_volume, reserved_funds = self._fit_open_volume_to_funds(volume, estimate_price)
            price_str = f"{estimate_price:.2f}" if estimate_price is not None else "未知"
            if actual_volume <= 0:
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 开空订单失败: 资金不足，请求{volume}手 参考价:{price_str}")
                self._mark_insufficient_funds(
                    f"{self.symbol} {self.kline_period} 开空订单失败：资金不足，请求{volume}手，参考价{price_str}"
                )
                return False
            if actual_volume < volume and log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 开空订单资金不足: {volume}手自动调整为{actual_volume}手")
            volume = actual_volume
            # 注意：如果是next_bar_open/high/low/close，价格可能为None，因为下一K线的数据尚未加载
            
            # 添加到待执行队列
            self.pending_orders.append({
                'action': "开空",
                'volume': volume,
                'price': price,  # 可能为None，将在执行时重新获取
                'reason': reason,
                'order_type': order_type,  # 保存订单类型
                'execution_time': self.current_idx + 1,  # 在下一K线执行
                'reserved_funds': reserved_funds,
            })
            
            if log_callback and debug_mode:
                price_str = f"{price:.2f}" if price is not None else "待确定"
                log_callback(f"{self.symbol} {self.kline_period} 添加待执行订单: 开空 {volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        
    def buycover(self, volume: Optional[int] = None, reason: str = "", log_callback=None, order_type='bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """
        平空仓
        
        Args:
            volume (int, optional): 交易数量，None表示平掉所有空仓
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值同buy函数
            offset_ticks: 价格偏移tick数
            price: 限价单价格（仅当order_type='limit'时有效）
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        if order_type == 'bar_close':
            # 当前K线收盘价下单，立即执行
            price = self.get_current_price()
            if price is None:
                return False
                
            if volume is None:
                volume = max(0, -self.current_pos)
            
            # 检查是否有空头持仓可平
            actual_volume = min(volume, max(0, -self.current_pos))
            if actual_volume <= 0:
                # 没有空头持仓可平，不记录交易
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 平空失败: 无空头持仓可平")
                return True
                
            self.target_pos = self.current_pos + actual_volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("平空", price, actual_volume, reason)
            self._sync_backtest_account()
            return True
        elif order_type == 'market':
            # 市价单，TICK数据买入使用卖一价格(AskPrice1)
            price = None
            if 'AskPrice1' in self.data.columns and self.current_idx < len(self.data):
                price = self.data.iloc[self.current_idx]['AskPrice1']
            else:
                price = self.get_current_price()
            
            if price is None:
                return False
                
            if volume is None:
                volume = max(0, -self.current_pos)
            
            # 检查是否有空头持仓可平
            actual_volume = min(volume, max(0, -self.current_pos))
            if actual_volume <= 0:
                # 没有空头持仓可平，不记录交易
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 市价平空失败: 无空头持仓可平")
                return True
                
            self.target_pos = self.current_pos + actual_volume
            if reason:
                self.set_signal_reason(reason)
            self._update_pos(log_callback)
            
            # 记录交易
            self.add_trade("平空", price, actual_volume, reason)
            
            if log_callback and debug_mode:
                log_callback(f"{self.symbol} {self.kline_period} 市价买平: {actual_volume}手 成交价:{price:.2f} 原因:{reason}")
            
            self._sync_backtest_account()
            return True
        else:
            # 下一K线价格下单，添加到待执行队列
            if price is None:
                price = self.get_price_by_type(order_type)
            # 注意：如果是next_bar_open/high/low/close，价格可能为None，因为下一K线的数据尚未加载
            
            if volume is None:
                volume = max(0, -self.current_pos)
            
            # 检查是否有空头持仓可平
            actual_volume = min(volume, max(0, -self.current_pos))
            if actual_volume <= 0:
                # 没有空头持仓可平，不添加订单
                if log_callback and debug_mode:
                    log_callback(f"{self.symbol} {self.kline_period} 平空订单失败: 无空头持仓可平")
                return True
            
            # 添加到待执行队列
            self.pending_orders.append({
                'action': "平空",
                'volume': actual_volume,
                'price': price,  # 可能为None，将在执行时重新获取
                'reason': reason,
                'order_type': order_type,  # 保存订单类型
                'execution_time': self.current_idx + 1  # 在下一K线执行
            })
            
            if log_callback and debug_mode:
                price_str = f"{price:.2f}" if price is not None else "待确定"
                log_callback(f"{self.symbol} {self.kline_period} 添加待执行订单: 平空 {actual_volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
            
            return True
        
    def reverse_pos(self, reason: str = "", log_callback=None, order_type='bar_close'):
        """
        反手（多转空，空转多）
        
        Args:
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值同buy函数
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        old_pos = self.current_pos
        if old_pos == 0:
            return True

        if old_pos > 0:
            reverse_volume = old_pos
            if order_type in ('bar_close', 'market'):
                if not self.sell(volume=reverse_volume, reason=reason, log_callback=log_callback, order_type=order_type):
                    return False
                return self.sellshort(volume=reverse_volume, reason=reason, log_callback=log_callback, order_type=order_type)

            price = self.get_price_by_type(order_type)
            self.pending_orders.append({
                'action': "平多",
                'volume': reverse_volume,
                'price': price,
                'reason': reason,
                'order_type': order_type,
                'execution_time': self.current_idx + 1
            })
            self.pending_orders.append({
                'action': "开空",
                'volume': reverse_volume,
                'price': price,
                'reason': reason,
                'order_type': order_type,
                'execution_time': self.current_idx + 1,
                'reserved_funds': 0.0,
                'defer_fund_check_until_execute': True,
            })
            if log_callback and debug_mode:
                price_str = f"{price:.2f}" if price is not None else "待确定"
                log_callback(f"{self.symbol} {self.kline_period} 添加待执行反手订单: 先平多后开空 {reverse_volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
            self._sync_backtest_account()
            return True

        reverse_volume = -old_pos
        if order_type in ('bar_close', 'market'):
            if not self.buycover(volume=reverse_volume, reason=reason, log_callback=log_callback, order_type=order_type):
                return False
            return self.buy(volume=reverse_volume, reason=reason, log_callback=log_callback, order_type=order_type)

        price = self.get_price_by_type(order_type)
        self.pending_orders.append({
            'action': "平空",
            'volume': reverse_volume,
            'price': price,
            'reason': reason,
            'order_type': order_type,
            'execution_time': self.current_idx + 1
        })
        self.pending_orders.append({
            'action': "开多",
            'volume': reverse_volume,
            'price': price,
            'reason': reason,
            'order_type': order_type,
            'execution_time': self.current_idx + 1,
            'reserved_funds': 0.0,
            'defer_fund_check_until_execute': True,
        })
        if log_callback and debug_mode:
            price_str = f"{price:.2f}" if price is not None else "待确定"
            log_callback(f"{self.symbol} {self.kline_period} 添加待执行反手订单: 先平空后开多 {reverse_volume}手 订单类型:{order_type} 预计价格:{price_str} 原因:{reason}")
        self._sync_backtest_account()
        return True
        
    def close_all(self, reason: str = "", log_callback=None, order_type='bar_close'):
        """
        平掉所有持仓
        
        Args:
            reason (str): 交易原因
            log_callback: 日志回调函数
            order_type (str): 订单类型，可选值同buy函数
        
        Returns:
            bool: 是否成功下单
        """
        # 获取debug模式设置
        debug_mode = getattr(log_callback, 'debug_mode', True) if log_callback else True
        
        if self.current_pos > 0:
            return self.sell(volume=None, reason=reason, log_callback=log_callback, order_type=order_type)
        elif self.current_pos < 0:
            return self.buycover(volume=None, reason=reason, log_callback=log_callback, order_type=order_type)
        return True  # 已经没有持仓
    
    # 数据访问方法
    def get_close(self) -> pd.Series:
        """获取收盘价序列"""
        df = self.get_klines()
        return df['close'] if 'close' in df.columns else pd.Series(dtype=float)  # type: ignore
    
    def get_open(self) -> pd.Series:
        """获取开盘价序列"""
        df = self.get_klines()
        return df['open'] if 'open' in df.columns else pd.Series(dtype=float)  # type: ignore
    
    def get_high(self) -> pd.Series:
        """获取最高价序列"""
        df = self.get_klines()
        return df['high'] if 'high' in df.columns else pd.Series(dtype=float)  # type: ignore
    
    def get_low(self) -> pd.Series:
        """获取最低价序列"""
        df = self.get_klines()
        return df['low'] if 'low' in df.columns else pd.Series(dtype=float)  # type: ignore
        
    def get_volume(self) -> pd.Series:
        """获取成交量序列"""
        df = self.get_klines()
        return df['volume'] if 'volume' in df.columns else pd.Series(dtype=float)  # type: ignore
        
    def get_klines(self, window: int = None) -> pd.DataFrame:
        """
        获取K线数据
        
        回测模式：返回从开始到当前索引的数据（避免未来数据泄露）
        实盘模式：返回所有缓存的数据（deque滚动窗口）
        
        跨周期场景下，高周期数据源自动返回原始K线（无ffill重复），
        确保 rolling 等指标在真实K线上计算。
        
        Args:
            window: 滑动窗口大小，None表示使用配置的lookback_bars，0表示不限制
            
        Returns:
            K线数据DataFrame，最多返回window条（从最近往前）
        """
        if not self.data.empty and hasattr(self, 'current_idx'):
            # 高周期数据源：返回原始K线（无ffill重复）
            if self._is_higher_tf and self.original_data is not None:
                current_time = self.data.index[self.current_idx]
                end = self.original_data.index.searchsorted(current_time, side='right')
                effective_window = window if window is not None else getattr(self, 'lookback_bars', 0)
                if effective_window > 0:
                    start = max(0, end - effective_window)
                    return self.original_data.iloc[start:end]
                return self.original_data.iloc[:end]

            # 回测模式：只返回到当前索引的数据
            end_idx = self.current_idx + 1
            
            # 确定窗口大小：优先使用传入参数，其次使用配置的lookback_bars
            effective_window = window if window is not None else getattr(self, 'lookback_bars', 0)
            
            # 如果设置了窗口限制（大于0），则只返回最近的window条数据
            if effective_window > 0:
                start_idx = max(0, end_idx - effective_window)
                return self.data.iloc[start_idx:end_idx]
            else:
                # 不限制，返回从开始到当前的所有数据
                return self.data.iloc[:end_idx]
        
        # 实盘模式或无索引：返回所有数据
        return self.data

    def get_tick(self) -> Optional[pd.Series]:
        """返回当前tick的所有字段（Series）"""
        if not self.data.empty and self.current_idx < len(self.data):
            return self.data.iloc[self.current_idx]
        return None

    def get_ticks(self, window: int = None) -> pd.DataFrame:
        """返回最近window条tick数据（DataFrame）
        
        Args:
            window: 滑动窗口大小，None表示使用配置的lookback_bars，0表示不限制
            
        Returns:
            最近window条tick数据
        """
        if not self.data.empty and self.current_idx < len(self.data):
            end_idx = self.current_idx + 1
            
            # 确定窗口大小：优先使用传入参数，其次使用配置的lookback_bars，最后默认100
            if window is not None:
                effective_window = window
            else:
                effective_window = getattr(self, 'lookback_bars', 0) or 100
            
            # 如果窗口大于0，限制返回数据量
            if effective_window > 0:
                start_idx = max(0, end_idx - effective_window)
                return self.data.iloc[start_idx:end_idx]
            else:
                return self.data.iloc[:end_idx]
        return pd.DataFrame()


class MultiDataSource:
    """
    多数据源管理类，用于管理多个数据源
    """
    
    def __init__(self):
        """初始化多数据源管理器"""
        self.data_sources = []
        self.log_callback = None
        
    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback
        
    def add_data_source(self, symbol: str, kline_period: str, adjust_type: str = '1', 
                        data: Optional[pd.DataFrame] = None, lookback_bars: int = 0,
                        slippage_ticks: int = 1, price_tick: float = 1.0) -> int:
        """
        添加数据源
        
        Args:
            symbol: 品种代码，如'rb888'
            kline_period: K线周期，如'1h', 'D'
            adjust_type: 复权类型，'0'表示不复权，'1'表示后复权
            data: 数据，如果为None则创建空数据源
            lookback_bars: K线回溯窗口大小，0表示不限制
            slippage_ticks: 滑点跳数，默认1跳
            price_tick: 最小变动价位，默认1.0
            
        Returns:
            数据源索引
        """
        data_source = DataSource(symbol, kline_period, adjust_type, lookback_bars=lookback_bars,
                                 slippage_ticks=slippage_ticks, price_tick=price_tick)
        if data is not None:
            data_source.set_data(data)
        self.data_sources.append(data_source)
        return len(self.data_sources) - 1
        
    def get_data_source(self, index: int) -> Optional[DataSource]:
        """获取指定索引的数据源"""
        if 0 <= index < len(self.data_sources):
            return self.data_sources[index]
        return None
        
    def get_data_sources_count(self) -> int:
        """获取数据源数量"""
        return len(self.data_sources)
        
    def __getitem__(self, index: int) -> Optional[DataSource]:
        """通过索引访问数据源"""
        return self.get_data_source(index)
        
    def __len__(self) -> int:
        """获取数据源数量"""
        return self.get_data_sources_count()
        
    def align_data(self, align_index: bool = True, fill_method: str = 'ffill'):
        """
        对齐所有数据源的数据
        
        跨周期防偷价：K线时间戳为周期起始时间（向下取整），高周期K线的 close
        在周期结束前不应对低周期策略可见。因此在对齐前，将高周期数据源的
        索引向前偏移一个自身周期，确保数据只在周期结束后才参与 ffill。
        
        Args:
            align_index: 是否对齐索引
            fill_method: 填充方法，可选值：'ffill', 'bfill', None
        """
        if len(self.data_sources) <= 1:
            return
            
        # 去除重复索引（数据库可能存在重复行）
        for ds in self.data_sources:
            if not ds.data.empty and ds.data.index.duplicated().any():
                ds.data = ds.data[~ds.data.index.duplicated(keep='last')]
        
        # 跨周期防偷价：高周期索引向前偏移一个周期
        periods = [_period_to_timedelta(ds.kline_period) for ds in self.data_sources]
        min_period = min(periods)
        for i, ds in enumerate(self.data_sources):
            if periods[i] > min_period and not ds.data.empty:
                ds.data.index = ds.data.index + periods[i]
                ds.original_data = ds.data.copy()
                ds._is_higher_tf = True
        
        # 收集所有数据源的索引
        all_indices = []
        for ds in self.data_sources:
            if not ds.data.empty:
                all_indices.append(ds.data.index)
                
        if not all_indices:
            return
            
        # 合并为统一索引
        common_index = all_indices[0]
        for idx in all_indices[1:]:
            common_index = common_index.union(idx)
            
        # 对齐所有数据源的数据
        for ds in self.data_sources:
            if not ds.data.empty:
                ds.data = ds.data.reindex(common_index)
                
                if fill_method:
                    if fill_method == 'ffill':
                        ds.data = ds.data.ffill()
                    elif fill_method == 'bfill':
                        ds.data = ds.data.bfill()
                    else:
                        ds.data = ds.data.fillna(method=fill_method)  # 保留兼容性 