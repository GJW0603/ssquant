import pandas as pd
import numpy as np

class BacktestResultCalculator:
    """回测结果计算器，负责计算交易统计、盈亏和绩效指标等"""
    
    def __init__(self, logger=None):
        """初始化结果计算器
        
        Args:
            logger: 日志管理器实例
        """
        self.logger = logger
        self.results = {}
    
    def calculate_performance(self, results):
        """计算回测性能指标
        
        Args:
            results: 回测结果字典
        
        Returns:
            包含性能指标的字典
        """
        if not results:
            return {}
            
        # 提取关键绩效指标
        performance = {}
        
        # 如果存在多个数据源，则计算平均指标
        total_return = 0
        annual_return = 0
        max_drawdown = 0
        max_drawdown_pct = 0
        sharpe_ratio = 0
        win_rate = 0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        profit_factor = 0
        
        # 计数器
        count = 0
        
        # 遍历所有结果
        for key, result in results.items():
            if isinstance(result, dict) and 'net_value' in result:
                count += 1
                
                # 确保净值不小于0.0001（防止出现负净值）
                net_value = max(0.0001, result.get('net_value', 1.0))
                result['net_value'] = net_value  # 修正结果中的净值
                
                # 累加绩效指标
                total_return += (net_value - 1.0) * 100  # 转换为百分比
                annual_return += result.get('annual_return', 0)
                max_drawdown += result.get('max_drawdown', 0)
                max_drawdown_pct += result.get('max_drawdown_pct', 0)
                sharpe_ratio += result.get('sharpe_ratio', 0)
                win_rate += result.get('win_rate', 0) * 100  # 转换为百分比
                
                # 累加交易统计
                total_trades += result.get('total_trades', 0)
                winning_trades += result.get('win_trades', 0)
                losing_trades += result.get('loss_trades', 0)
                profit_factor += result.get('profit_factor', 0)
        
        # 计算平均值
        if count > 0:
            performance['total_return'] = total_return / count
            performance['annual_return'] = annual_return / count
            performance['max_drawdown'] = max_drawdown / count
            performance['max_drawdown_pct'] = max_drawdown_pct / count
            performance['sharpe_ratio'] = sharpe_ratio / count
            performance['win_rate'] = win_rate / count
            
            # 交易统计
            trade_stats = {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'profit_factor': profit_factor / count if count > 0 else 0
            }
            performance['trade_stats'] = trade_stats
        
        # 添加性能指标到结果中
        results['performance'] = performance
        
        return performance
    
    def log(self, message):
        """记录日志
        
        Args:
            message: 日志消息
        """
        if self.logger:
            self.logger.log_message(message)
        else:
            print(message)
    
    def calculate_results(self, multi_data_source, symbol_configs):
        """计算回测结果
        
        Args:
            multi_data_source: 多数据源实例
            symbol_configs: 品种配置字典
            
        Returns:
            results: 回测结果字典
        """
        results = {}
        
        # 资金分配：统计每个品种的 initial_capital 和对应的数据源数量
        num_data_sources = len(multi_data_source.data_sources)
        _symbol_ds_info = {}
        for ds in multi_data_source.data_sources:
            sc = symbol_configs.get(ds.symbol, {})
            cap = sc.get('initial_capital', 100000.0)
            if ds.symbol not in _symbol_ds_info:
                _symbol_ds_info[ds.symbol] = {'capital': cap, 'count': 0}
            _symbol_ds_info[ds.symbol]['count'] += 1
        # 判断分配模式：所有品种 initial_capital 相同 → 共享总资金均分；不同 → 按品种独立分配
        _unique_capitals = set(v['capital'] for v in _symbol_ds_info.values())
        _shared_capital_mode = len(_unique_capitals) == 1 and num_data_sources > 1
        
        # 遍历所有数据源
        for ds_idx, ds in enumerate(multi_data_source.data_sources):
            # 获取交易记录
            trades = ds.trades
            result_end_idx = int(getattr(ds, 'result_end_idx', len(ds.data)) or 0)
            result_end_idx = max(0, min(result_end_idx, len(ds.data)))
            effective_data = ds.data.iloc[:result_end_idx].copy() if result_end_idx > 0 else ds.data.iloc[0:0].copy()
            
            if not trades:
                self.log(f"数据源 #{ds_idx} ({ds.symbol} {ds.kline_period}) 没有交易记录")
                continue
            if effective_data.empty:
                self.log(f"数据源 #{ds_idx} ({ds.symbol} {ds.kline_period}) 没有可用于生成报告的回测区间")
                continue
            
            # 获取品种配置
            symbol_config = symbol_configs.get(ds.symbol, {
                'commission': 0.0003,  # 手续费率
                'margin_rate': 0.1,  # 保证金率
                'contract_multiplier': 10,  # 合约乘数
                'initial_capital': 100000.0  # 初始资金
            })
            commission_rate = symbol_config.get('commission', 0.0003)
            margin_rate = symbol_config.get('margin_rate', 0.1)
            contract_multiplier = symbol_config.get('contract_multiplier', 10)
            _ds_allocated = getattr(ds, '_allocated_capital', None)
            if _ds_allocated is not None:
                initial_capital = _ds_allocated
            else:
                raw_capital = symbol_config.get('initial_capital', 100000.0)
                if _shared_capital_mode:
                    initial_capital = raw_capital / num_data_sources
                elif num_data_sources > 1:
                    initial_capital = raw_capital / _symbol_ds_info[ds.symbol]['count']
                else:
                    initial_capital = raw_capital
            
            # 获取固定金额手续费（元/手）
            commission_per_lot = symbol_config.get('commission_per_lot', 0)
            commission_close_per_lot = symbol_config.get('commission_close_per_lot', 0)
            commission_close_today_per_lot = symbol_config.get('commission_close_today_per_lot', 0)
            
            # 判断手续费计算方式：
            # - 如果费率 > 1e-05（有意义的费率），则使用费率计算（如螺纹钢 0.000101）
            # - 如果费率 ≈ 1e-06（无意义占位符）且固定金额 > 0，则使用固定金额（如黄金 10元/手）
            use_fixed_commission = commission_rate < 1e-05 and commission_per_lot > 0.1
            
            # ===== 基于均价跟踪计算每笔交易的盈亏（支持加仓/部分平仓/复合反手） =====
            _long_pos = 0
            _long_avg_price = 0.0
            _short_pos = 0
            _short_avg_price = 0.0

            def _calc_trade_commission(action, price, vol):
                """根据动作类型（开仓/平仓）计算手续费"""
                is_close = action in ('平多', '平空')
                if use_fixed_commission:
                    per_lot = commission_close_per_lot if is_close else commission_per_lot
                    return per_lot * vol
                return price * vol * contract_multiplier * commission_rate

            for trade in trades:
                action = trade['action']
                price = trade['price']
                volume = trade['volume']
                _slippage_per_unit = trade.get('slippage_cost', 0)

                if action == '开多':
                    trade['slippage'] = _slippage_per_unit * volume * contract_multiplier
                    comm = _calc_trade_commission(action, price, volume)
                    trade['commission'] = comm
                    trade['points_profit'] = 0
                    trade['amount_profit'] = 0
                    trade['margin'] = price * volume * contract_multiplier * margin_rate
                    if _long_pos > 0:
                        _long_avg_price = (_long_pos * _long_avg_price + volume * price) / (_long_pos + volume)
                    else:
                        _long_avg_price = price
                    _long_pos += volume

                elif action == '平多':
                    actual_vol = min(volume, _long_pos)
                    if actual_vol <= 0:
                        trade['commission'] = 0
                        trade['points_profit'] = 0
                        trade['amount_profit'] = 0
                        trade['net_profit'] = 0
                        trade['roi'] = 0
                        trade['profit'] = 0
                        trade['slippage'] = 0
                        trade['margin'] = 0
                        continue
                    trade['slippage'] = _slippage_per_unit * actual_vol * contract_multiplier
                    comm = _calc_trade_commission(action, price, actual_vol)
                    pts = price - _long_avg_price
                    amt = pts * actual_vol * contract_multiplier
                    net = amt - comm
                    mgn = max(_long_avg_price, price) * actual_vol * contract_multiplier * margin_rate
                    trade['commission'] = comm
                    trade['points_profit'] = pts
                    trade['amount_profit'] = amt
                    trade['net_profit'] = net
                    trade['roi'] = net / mgn * 100 if mgn > 0 else 0
                    trade['profit'] = net
                    trade['margin'] = mgn
                    _long_pos -= actual_vol
                    if _long_pos <= 0:
                        _long_pos = 0
                        _long_avg_price = 0.0

                elif action == '开空':
                    trade['slippage'] = _slippage_per_unit * volume * contract_multiplier
                    comm = _calc_trade_commission(action, price, volume)
                    trade['commission'] = comm
                    trade['points_profit'] = 0
                    trade['amount_profit'] = 0
                    trade['margin'] = price * volume * contract_multiplier * margin_rate
                    if _short_pos > 0:
                        _short_avg_price = (_short_pos * _short_avg_price + volume * price) / (_short_pos + volume)
                    else:
                        _short_avg_price = price
                    _short_pos += volume

                elif action == '平空':
                    actual_vol = min(volume, _short_pos)
                    if actual_vol <= 0:
                        trade['commission'] = 0
                        trade['points_profit'] = 0
                        trade['amount_profit'] = 0
                        trade['net_profit'] = 0
                        trade['roi'] = 0
                        trade['profit'] = 0
                        trade['slippage'] = 0
                        trade['margin'] = 0
                        continue
                    trade['slippage'] = _slippage_per_unit * actual_vol * contract_multiplier
                    comm = _calc_trade_commission(action, price, actual_vol)
                    pts = _short_avg_price - price
                    amt = pts * actual_vol * contract_multiplier
                    net = amt - comm
                    mgn = max(_short_avg_price, price) * actual_vol * contract_multiplier * margin_rate
                    trade['commission'] = comm
                    trade['points_profit'] = pts
                    trade['amount_profit'] = amt
                    trade['net_profit'] = net
                    trade['roi'] = net / mgn * 100 if mgn > 0 else 0
                    trade['profit'] = net
                    trade['margin'] = mgn
                    _short_pos -= actual_vol
                    if _short_pos <= 0:
                        _short_pos = 0
                        _short_avg_price = 0.0

                elif action == '平多开空':
                    close_vol = min(volume, _long_pos)
                    open_vol = close_vol
                    close_comm = 0
                    pts = 0
                    amt = 0
                    if close_vol > 0:
                        close_comm = _calc_trade_commission('平多', price, close_vol)
                        pts = price - _long_avg_price
                        amt = pts * close_vol * contract_multiplier
                        _long_pos -= close_vol
                        if _long_pos <= 0:
                            _long_pos = 0
                            _long_avg_price = 0.0
                    open_comm = _calc_trade_commission('开空', price, open_vol) if open_vol > 0 else 0
                    if open_vol > 0:
                        if _short_pos > 0:
                            _short_avg_price = (_short_pos * _short_avg_price + open_vol * price) / (_short_pos + open_vol)
                        else:
                            _short_avg_price = price
                        _short_pos += open_vol
                    total_comm = close_comm + open_comm
                    net = amt - total_comm if close_vol > 0 else 0
                    mgn = price * open_vol * contract_multiplier * margin_rate if open_vol > 0 else 0
                    trade['slippage'] = trade.get('slippage_cost', 0) * (close_vol + open_vol) * contract_multiplier
                    trade['commission'] = total_comm
                    trade['points_profit'] = pts
                    trade['amount_profit'] = amt
                    trade['net_profit'] = net
                    trade['roi'] = net / mgn * 100 if mgn > 0 and close_vol > 0 else 0
                    trade['profit'] = net
                    trade['margin'] = mgn

                elif action == '平空开多':
                    close_vol = min(volume, _short_pos)
                    open_vol = close_vol
                    close_comm = 0
                    pts = 0
                    amt = 0
                    if close_vol > 0:
                        close_comm = _calc_trade_commission('平空', price, close_vol)
                        pts = _short_avg_price - price
                        amt = pts * close_vol * contract_multiplier
                        _short_pos -= close_vol
                        if _short_pos <= 0:
                            _short_pos = 0
                            _short_avg_price = 0.0
                    open_comm = _calc_trade_commission('开多', price, open_vol) if open_vol > 0 else 0
                    if open_vol > 0:
                        if _long_pos > 0:
                            _long_avg_price = (_long_pos * _long_avg_price + open_vol * price) / (_long_pos + open_vol)
                        else:
                            _long_avg_price = price
                        _long_pos += open_vol
                    total_comm = close_comm + open_comm
                    net = amt - total_comm if close_vol > 0 else 0
                    mgn = price * open_vol * contract_multiplier * margin_rate if open_vol > 0 else 0
                    trade['slippage'] = trade.get('slippage_cost', 0) * (close_vol + open_vol) * contract_multiplier
                    trade['commission'] = total_comm
                    trade['points_profit'] = pts
                    trade['amount_profit'] = amt
                    trade['net_profit'] = net
                    trade['roi'] = net / mgn * 100 if mgn > 0 and close_vol > 0 else 0
                    trade['profit'] = net
                    trade['margin'] = mgn

                else:
                    trade.setdefault('commission', 0)
                    trade.setdefault('points_profit', 0)
                    trade.setdefault('amount_profit', 0)
                    trade.setdefault('slippage', 0)
                    trade.setdefault('margin', 0)

            # ===== 统计交易数据（包含复合反手动作） =====
            _close_actions = ('平多', '平空', '平多开空', '平空开多')
            total_trades = sum(1 for t in trades if t['action'] in _close_actions)
            win_trades = sum(1 for t in trades if t.get('net_profit', 0) > 0 and t['action'] in _close_actions)
            loss_trades = sum(1 for t in trades if t.get('net_profit', 0) < 0 and t['action'] in _close_actions)
            win_rate = win_trades / (win_trades + loss_trades) if (win_trades + loss_trades) > 0 else 0
            
            total_points_profit = sum(t.get('points_profit', 0) for t in trades)
            total_amount_profit = sum(t.get('amount_profit', 0) for t in trades)
            total_commission = sum(t.get('commission', 0) for t in trades)
            total_slippage = sum(t.get('slippage', 0) for t in trades)
            total_net_profit = sum(t.get('net_profit', 0) for t in trades)
            
            _total_win_pnl = sum(t.get('net_profit', 0) for t in trades if t.get('net_profit', 0) > 0 and t['action'] in _close_actions)
            _total_loss_pnl = abs(sum(t.get('net_profit', 0) for t in trades if t.get('net_profit', 0) < 0 and t['action'] in _close_actions))
            avg_win = _total_win_pnl / win_trades if win_trades > 0 else 0
            avg_loss = -(_total_loss_pnl / loss_trades) if loss_trades > 0 else 0
            
            if _total_loss_pnl > 0:
                profit_factor = _total_win_pnl / _total_loss_pnl
            else:
                profit_factor = float('inf') if _total_win_pnl > 0 else 0
            
            # 修改权益曲线计算方法，考虑持仓盈亏
            equity_curve = pd.Series(float(initial_capital), index=effective_data.index, dtype=float)  # 净利润曲线（扣除所有成本）
            gross_equity_curve = pd.Series(float(initial_capital), index=effective_data.index, dtype=float)  # 毛利润曲线（完全不扣除成本）
            available_cash = initial_capital  # 可用资金（未被占用的资金）
            total_margin = 0  # 总保证金占用
            total_equity = initial_capital  # 总权益（可用资金 + 保证金 + 浮动盈亏）
            # 累计成本追踪（用于计算毛利润曲线）
            cumulative_commission = 0  # 累计手续费
            cumulative_slippage = 0  # 累计滑点成本
            
            # 持仓管理
            long_pos = 0  # 多头持仓量
            long_avg_price = 0  # 多头平均持仓价格
            short_pos = 0  # 空头持仓量
            short_avg_price = 0  # 空头平均持仓价格
            
            # 按时间排序交易记录并创建副本，避免修改原始数据
            sorted_trades = sorted(trades.copy(), key=lambda x: x['datetime'])
            
            # 遍历每个时间点
            for i, date in enumerate(effective_data.index):
                row = effective_data.iloc[i]
                # K线数据使用close，TICK数据使用LastPrice
                if 'close' in row:
                    current_price = row['close']
                elif 'LastPrice' in row:
                    current_price = row['LastPrice']
                elif 'BidPrice1' in row and 'AskPrice1' in row:
                    current_price = (row['BidPrice1'] + row['AskPrice1']) / 2
                else:
                    raise KeyError("数据中未找到价格字段（close/LastPrice/BidPrice1+AskPrice1）")
                
                # 处理当前日期的所有交易
                trades_to_process = [t for t in sorted_trades if t['datetime'] <= date]
                trades_to_remove = []  # 存储需要移除的交易索引
                
                for trade in trades_to_process:
                    if trade['action'] == '开多':
                        # 计算开仓成本和保证金
                        volume = trade['volume']
                        price = trade['price']
                        position_cost = price * volume * contract_multiplier
                        margin_required = position_cost * margin_rate
                        commission = trade.get('commission', 0)
                        
                        # 更新资金（净利润：扣除手续费）
                        available_cash -= (margin_required + commission)
                        total_margin += margin_required
                        
                        # 累计成本
                        cumulative_commission += commission
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_slippage += slippage_cost
                        
                        # 更新多头持仓和平均价格
                        if long_pos > 0:
                            # 计算新的加权平均持仓价格
                            long_avg_price = (long_pos * long_avg_price + volume * price) / (long_pos + volume)
                        else:
                            long_avg_price = price
                        long_pos += volume
                        
                    elif trade['action'] == '平多':
                        # 获取平仓数量和价格
                        volume = min(trade['volume'], long_pos)  # 确保不超过实际持仓
                        if volume <= 0:
                            continue  # 无多头持仓可平，跳过
                            
                        price = trade['price']
                        commission = trade.get('commission', 0)
                        
                        # 计算平仓后释放的保证金
                        position_value = long_avg_price * volume * contract_multiplier
                        margin_released = position_value * margin_rate
                        
                        # 计算平仓盈亏
                        close_profit = (price - long_avg_price) * volume * contract_multiplier
                        
                        # 更新资金（净利润：扣除手续费）
                        available_cash += (margin_released + close_profit - commission)
                        total_margin -= margin_released
                        
                        # 累计成本
                        cumulative_commission += commission
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_slippage += slippage_cost
                        
                        # 更新多头持仓
                        long_pos -= volume
                        # 如果完全平仓，重置平均价格
                        if long_pos <= 0:
                            long_pos = 0
                            long_avg_price = 0
                        
                    elif trade['action'] == '开空':
                        # 计算开仓成本和保证金
                        volume = trade['volume']
                        price = trade['price']
                        position_cost = price * volume * contract_multiplier
                        margin_required = position_cost * margin_rate
                        commission = trade.get('commission', 0)
                        
                        # 更新资金（净利润：扣除手续费）
                        available_cash -= (margin_required + commission)
                        total_margin += margin_required
                        
                        # 累计成本
                        cumulative_commission += commission
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_slippage += slippage_cost
                        
                        # 更新空头持仓和平均价格
                        if short_pos > 0:
                            # 计算新的加权平均持仓价格
                            short_avg_price = (short_pos * short_avg_price + volume * price) / (short_pos + volume)
                        else:
                            short_avg_price = price
                        short_pos += volume
                        
                    elif trade['action'] == '平空':
                        # 获取平仓数量和价格
                        volume = min(trade['volume'], short_pos)  # 确保不超过实际持仓
                        if volume <= 0:
                            continue  # 无空头持仓可平，跳过
                            
                        price = trade['price']
                        commission = trade.get('commission', 0)
                        
                        # 计算平仓后释放的保证金
                        position_value = short_avg_price * volume * contract_multiplier
                        margin_released = position_value * margin_rate
                        
                        # 计算平仓盈亏
                        close_profit = (short_avg_price - price) * volume * contract_multiplier
                        
                        # 更新资金（净利润：扣除手续费）
                        available_cash += (margin_released + close_profit - commission)
                        total_margin -= margin_released
                        
                        # 累计成本
                        cumulative_commission += commission
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_slippage += slippage_cost
                        
                        # 更新空头持仓
                        short_pos -= volume
                        # 如果完全平仓，重置平均价格
                        if short_pos <= 0:
                            short_pos = 0
                            short_avg_price = 0

                    elif trade['action'] == '平多开空':
                        volume = trade['volume']
                        price = trade['price']
                        commission = trade.get('commission', 0)
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_commission += commission
                        cumulative_slippage += slippage_cost
                        close_vol = min(volume, long_pos)
                        open_vol = close_vol
                        if close_vol > 0:
                            position_value = long_avg_price * close_vol * contract_multiplier
                            margin_released = position_value * margin_rate
                            close_profit = (price - long_avg_price) * close_vol * contract_multiplier
                            available_cash += (margin_released + close_profit)
                            total_margin -= margin_released
                            long_pos -= close_vol
                            if long_pos <= 0:
                                long_pos = 0
                                long_avg_price = 0
                        available_cash -= commission
                        if open_vol > 0:
                            position_cost = price * open_vol * contract_multiplier
                            margin_required = position_cost * margin_rate
                            available_cash -= margin_required
                            total_margin += margin_required
                            if short_pos > 0:
                                short_avg_price = (short_pos * short_avg_price + open_vol * price) / (short_pos + open_vol)
                            else:
                                short_avg_price = price
                            short_pos += open_vol

                    elif trade['action'] == '平空开多':
                        volume = trade['volume']
                        price = trade['price']
                        commission = trade.get('commission', 0)
                        slippage_cost = trade.get('slippage', 0)
                        cumulative_commission += commission
                        cumulative_slippage += slippage_cost
                        close_vol = min(volume, short_pos)
                        open_vol = close_vol
                        if close_vol > 0:
                            position_value = short_avg_price * close_vol * contract_multiplier
                            margin_released = position_value * margin_rate
                            close_profit = (short_avg_price - price) * close_vol * contract_multiplier
                            available_cash += (margin_released + close_profit)
                            total_margin -= margin_released
                            short_pos -= close_vol
                            if short_pos <= 0:
                                short_pos = 0
                                short_avg_price = 0
                        available_cash -= commission
                        if open_vol > 0:
                            position_cost = price * open_vol * contract_multiplier
                            margin_required = position_cost * margin_rate
                            available_cash -= margin_required
                            total_margin += margin_required
                            if long_pos > 0:
                                long_avg_price = (long_pos * long_avg_price + open_vol * price) / (long_pos + open_vol)
                            else:
                                long_avg_price = price
                            long_pos += open_vol
                    
                    # 标记交易为待移除，而不是直接移除
                    trades_to_remove.append(trade)
                
                # 在循环之外移除已处理的交易
                for trade in trades_to_remove:
                    if trade in sorted_trades:
                        sorted_trades.remove(trade)
                
                # 计算多头浮动盈亏
                long_floating_pnl = 0
                if long_pos > 0:
                    long_floating_pnl = (current_price - long_avg_price) * long_pos * contract_multiplier
                
                # 计算空头浮动盈亏
                short_floating_pnl = 0
                if short_pos > 0:
                    short_floating_pnl = (short_avg_price - current_price) * short_pos * contract_multiplier
                
                # 计算总浮动盈亏
                total_floating_pnl = long_floating_pnl + short_floating_pnl
                
                # 计算当前总权益（净利润：已扣除成本）
                total_equity = available_cash + total_margin + total_floating_pnl
                
                # 计算毛利润总权益（完全不扣除成本：净权益 + 累计手续费 + 累计滑点）
                gross_total_equity = total_equity + cumulative_commission + cumulative_slippage
                
                # 更新权益曲线
                equity_curve[date] = total_equity
                gross_equity_curve[date] = gross_total_equity
            
            # 计算期末权益和净值
            final_equity = equity_curve.iloc[-1] if not equity_curve.empty else initial_capital
            gross_final_equity = gross_equity_curve.iloc[-1] if not gross_equity_curve.empty else initial_capital
            
            # 确保期末权益不小于0.01（为了避免负净值）
            final_equity = max(0.01, final_equity)
            gross_final_equity = max(0.01, gross_final_equity)
            
            net_value = final_equity / initial_capital
            
            # 重新计算利润指标，确保与权益曲线一致
            # 净利润 = 期末权益 - 初始资金（基于 equity_curve，已扣除手续费和滑点）
            total_net_profit = final_equity - initial_capital
            # 毛利润 = 净利润 + 手续费 + 滑点（完全不含任何成本的原始盈亏）
            total_amount_profit = total_net_profit + total_commission + total_slippage
            
            # 计算最大回撤（使用修改后的权益曲线）
            if not equity_curve.empty and equity_curve.max() > 0:
                # 对权益曲线进行修正，不允许出现负值
                equity_curve = equity_curve.clip(lower=0.01)
                
                cummax = equity_curve.cummax()
                drawdown = (cummax - equity_curve)
                max_drawdown = drawdown.max()
                max_drawdown_pct = (drawdown / cummax).max() * 100
            else:
                max_drawdown = 0
                max_drawdown_pct = 0
            
            # 计算年化收益率和夏普比率
            # 先将权益曲线按日聚合，避免不同K线周期导致的计算偏差
            annual_return = 0
            sharpe_ratio = 0
            
            if not equity_curve.empty and len(equity_curve) > 1:
                # 将权益曲线按日聚合（取每日最后一个值）
                equity_with_date = pd.Series(equity_curve.values, index=effective_data.index[:len(equity_curve)])
                daily_equity = equity_with_date.resample('D').last().dropna()
                
                if len(daily_equity) > 1:
                    # 计算日收益率（百分比形式）
                    daily_returns = daily_equity.pct_change().dropna()
                    
                    # 计算实际交易天数
                    actual_trading_days = len(daily_equity)
                    
                    # 年化收益率：(期末/期初)^(250/交易天数) - 1
                    if actual_trading_days > 0 and daily_equity.iloc[0] > 0:
                        total_return = (daily_equity.iloc[-1] / daily_equity.iloc[0]) - 1
                        # 简单年化：总收益率 / 年数
                        years = actual_trading_days / 250
                        if years > 0:
                            annual_return = (total_return / years) * 100
                    
                    # 夏普比率：(日收益率均值 - 无风险日利率) / 日收益率标准差 * √250
                    # 假设无风险年利率为3%
                    risk_free_daily = 0.03 / 250
                    
                    if len(daily_returns) > 0 and daily_returns.std() > 0:
                        excess_return = daily_returns.mean() - risk_free_daily
                        sharpe_ratio = excess_return / daily_returns.std() * np.sqrt(250)
                else:
                    # 只有一天数据，无法计算
                    annual_return = 0
                    sharpe_ratio = 0
            
            # 保存结果
            ds_results = {
                'symbol': ds.symbol,
                'kline_period': ds.kline_period,
                'adjust_type': ds.adjust_type,
                'contract_multiplier': contract_multiplier,  # 添加合约乘数到结果
                'total_trades': total_trades,
                'win_trades': win_trades,
                'loss_trades': loss_trades,
                'win_rate': win_rate,
                'total_points_profit': total_points_profit,
                'total_amount_profit': total_amount_profit,
                'total_commission': total_commission,
                'total_slippage': total_slippage,  # 总滑点成本
                'total_net_profit': total_net_profit,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'initial_capital': initial_capital,
                'final_equity': final_equity,
                'net_value': net_value,
                'max_drawdown': max_drawdown,
                'max_drawdown_pct': max_drawdown_pct,
                'annual_return': annual_return,
                'sharpe_ratio': sharpe_ratio,
                'trades': trades,
                'data': effective_data,
                'equity_curve': equity_curve,
                'gross_equity_curve': gross_equity_curve  # 毛利润曲线（不扣除成本）
            }
            
            # 添加到结果字典
            key = f"{ds.symbol}_{ds.kline_period}_{'不复权' if ds.adjust_type == '0' else '后复权'}"
            results[key] = ds_results
            
            # 打印结果摘要
            self.log(f"\n数据源 #{ds_idx} ({ds.symbol} {ds.kline_period}) 回测结果:")
            self.log(f"总交易次数: {total_trades}")
            self.log(f"盈利交易: {win_trades}, 亏损交易: {loss_trades}")
            self.log(f"胜率: {win_rate:.2%}")
            self.log(f"初始权益: {initial_capital:.2f}")
            self.log(f"期末权益: {final_equity:.2f}")
            self.log(f"净值: {net_value:.4f}")
            self.log(f"总点数盈亏: {total_points_profit:.2f}")
            self.log(f"毛利润(不含成本): {total_amount_profit:.2f}")
            self.log(f"总手续费: {total_commission:.2f}")
            self.log(f"总滑点成本: {total_slippage:.2f}")
            self.log(f"净利润(扣除成本): {total_net_profit:.2f}")
            self.log(f"平均盈利: {avg_win:.2f}")
            self.log(f"平均亏损: {avg_loss:.2f}")
            self.log(f"盈亏比: {profit_factor:.2f}")
            self.log(f"最大回撤: {max_drawdown:.2f} ({max_drawdown_pct:.2f})")
            self.log(f"年化收益率: {annual_return:.2f}%")
            self.log(f"夏普比率: {sharpe_ratio:.2f}")
            
            # 打印交易明细
            self.log("\n交易明细:")
            for j, trade in enumerate(trades):
                trade_time = trade['datetime']
                action = trade['action']
                price = trade['price']
                volume = trade['volume']
                points_profit = trade.get('points_profit', 0)
                amount_profit = trade.get('amount_profit', 0)
                commission = trade.get('commission', 0)
                net_profit = trade.get('net_profit', 0)
                roi = trade.get('roi', 0)
                reason = trade.get('reason', '')
                
                # 只打印平仓交易的盈亏
                if action in ['平多', '平空', '平多开空', '平空开多']:
                    profit_info = f" 点数盈亏:{points_profit:.2f} 金额盈亏:{amount_profit:.2f} 手续费:{commission:.2f} 净盈亏:{net_profit:.2f} ROI:{roi:.2f}%"
                else:
                    profit_info = f" 手续费:{commission:.2f}"
                
                self.log(f"{j+1}. {trade_time} {action} {volume}手 价格:{price:.2f}{profit_info}")
        
        self.results = results
        return results
    
    def get_summary(self, results=None):
        """获取回测结果摘要
        
        Args:
            results: 回测结果字典，如果为None则使用内部结果
            
        Returns:
            summary: 回测结果摘要DataFrame
        """
        if results is None:
            results = self.results
            
        if not results:
            return None
        
        summary_data = []
        for key, result in results.items():
            if not isinstance(result, dict) or 'symbol' not in result:
                continue
            summary_data.append({
                '数据集': key,
                '品种': result['symbol'],
                '周期': result['kline_period'],
                '复权类型': '不复权' if result['adjust_type'] == '0' else '后复权',
                '总交易次数': result['total_trades'],
                '盈利交易': result['win_trades'],
                '亏损交易': result['loss_trades'],
                '胜率': result['win_rate'],
                '初始权益': result.get('initial_capital', 100000.0),
                '期末权益': result.get('final_equity', 100000.0),
                '净值': result.get('net_value', 1.0),
                '总点数盈亏': result.get('total_points_profit', 0),
                '总金额盈亏': result.get('total_amount_profit', 0),
                '总手续费': result.get('total_commission', 0),
                '总净盈亏': result.get('total_net_profit', 0),
                '最大回撤': result.get('max_drawdown', 0),
                '最大回撤率': result.get('max_drawdown_pct', 0),
                '年化收益率': result.get('annual_return', 0),
                '夏普比率': result.get('sharpe_ratio', 0)
            })
        
        return pd.DataFrame(summary_data)
    
    def get_results(self):
        """获取回测结果字典
        
        Returns:
            results: 回测结果字典
        """
        return self.results 