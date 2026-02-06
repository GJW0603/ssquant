#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实盘交易适配器
将CTP实盘交易接口适配为与回测一致的API调用方式
支持SIMNOW模拟和实盘交易
"""

import time
import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union, TYPE_CHECKING
from collections import deque
import threading

from ..api.strategy_api import StrategyAPI

if TYPE_CHECKING:
    from ..pyctp.simnow_client import SIMNOWClient
    from ..pyctp.real_trading_client import RealTradingClient


import queue

class DataRecorder:
    """数据记录器 - 实盘行情落盘（支持CSV和DB双存储，异步队列写入）"""
    
    # 类级别的共享写入队列和后台线程（所有记录器共用）
    _write_queue = None
    _write_thread = None
    _running = False
    _init_lock = threading.Lock()  # 初始化锁，防止竞态条件
    
    @classmethod
    def _init_write_thread(cls):
        """初始化后台写入线程（只初始化一次，线程安全）"""
        if cls._write_thread is None:
            with cls._init_lock:  # 双重检查锁定
                if cls._write_thread is None:
                    cls._write_queue = queue.Queue()
                    cls._running = True
                    cls._write_thread = threading.Thread(target=cls._write_worker, daemon=True)
                    cls._write_thread.start()
                    print("[数据记录器] 后台写入线程已启动")
    
    @classmethod
    def _write_worker(cls):
        """后台写入工作线程"""
        while cls._running:
            try:
                # 等待队列中的任务，超时1秒
                task = cls._write_queue.get(timeout=1)
                if task is None:  # 退出信号
                    break
                
                task_type, data, params = task
                
                if task_type == 'tick_csv':
                    cls._do_write_csv(data, params['file_path'])
                elif task_type == 'tick_db':
                    cls._do_write_db(data, params['db_path'], params['table_name'])
                elif task_type == 'kline_csv':
                    cls._do_write_csv(data, params['file_path'])
                elif task_type == 'kline_db':
                    cls._do_write_db(data, params['db_path'], params['table_name'], log=True)
                
                cls._write_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[数据记录器] 后台写入错误: {e}")
    
    @classmethod
    def _do_write_csv(cls, data: Dict, file_path: str):
        """实际执行CSV写入"""
        try:
            df = pd.DataFrame([data])
            if os.path.exists(file_path):
                df.to_csv(file_path, mode='a', header=False, index=False)
            else:
                df.to_csv(file_path, index=False)
        except Exception as e:
            print(f"[数据记录器] CSV写入失败: {e}")
    
    @classmethod
    def _do_write_db(cls, data: Dict, db_path: str, table_name: str, log: bool = False):
        """实际执行DB写入（使用快速写入，不做去重检查）"""
        try:
            from ..data.api_data_fetcher import append_kline_fast
            new_count = append_kline_fast(data, db_path, table_name)
            if log and new_count > 0:
                # 提取K线详细信息
                dt = data.get('datetime', '')
                o = data.get('open', 0)
                h = data.get('high', 0)
                l = data.get('low', 0)
                c = data.get('close', 0)
                v = data.get('volume', 0)
                oi = data.get('cumulative_openint', 0) or 0
                oi_change = data.get('openint', 0) or 0
                oi_str = f"+{oi_change:.0f}" if oi_change >= 0 else f"{oi_change:.0f}"
                print(f"[K线写入] {table_name} | {dt} | O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f} V:{v:.0f} OI:{oi:.0f}({oi_str})")
        except Exception as e:
            print(f"[数据记录器] DB写入失败 {table_name}: {e}")
    
    @classmethod
    def stop_write_thread(cls):
        """停止后台写入线程"""
        if cls._write_thread and cls._running:
            cls._running = False
            cls._write_queue.put(None)  # 发送退出信号
            cls._write_thread.join(timeout=5)
            print("[数据记录器] 后台写入线程已停止")
    
    def __init__(self, symbol: str, kline_period: str = "1m",
                 save_path: str = "./live_data",
                 db_path: str = "data_cache/backtest_data.db",
                 save_kline_csv: bool = False,
                 save_kline_db: bool = False,
                 save_tick_csv: bool = False,
                 save_tick_db: bool = False,
                 adjust_type: str = "0"):
        """
        初始化数据记录器
        
        Args:
            symbol: 合约代码（具体合约，如 rb2601）
            kline_period: K线周期（用于DB表名，如 1m, 5m, 1d）
            save_path: CSV保存路径
            db_path: 数据库路径
            save_kline_csv: 是否保存K线到CSV
            save_kline_db: 是否保存K线到数据库
            save_tick_csv: 是否保存TICK到CSV
            save_tick_db: 是否保存TICK到数据库
            adjust_type: 复权类型 ('0'=不复权/raw, '1'=后复权/hfq)
        """
        self.symbol = symbol
        self.kline_period = kline_period
        self.save_path = save_path
        self.db_path = db_path
        self.adjust_type = adjust_type
        
        # 四个独立开关
        self.save_kline_csv = save_kline_csv
        self.save_kline_db = save_kline_db
        self.save_tick_csv = save_tick_csv
        self.save_tick_db = save_tick_db
        
        # 推导主连符号（用于DB存储）
        from ..data.contract_mapper import ContractMapper
        self.continuous_symbol = ContractMapper.get_continuous_symbol(symbol)
        
        # 创建CSV保存目录
        if save_kline_csv or save_tick_csv:
            os.makedirs(save_path, exist_ok=True)
        
        # CSV文件名（K线文件包含周期，如 au2602_1m_kline_20260119.csv）
        date_str = datetime.now().strftime("%Y%m%d")
        self.tick_file = os.path.join(save_path, f"{symbol}_tick_{date_str}.csv")
        self.kline_file = os.path.join(save_path, f"{symbol}_{kline_period}_kline_{date_str}.csv")
        
        # 根据复权类型确定K线表名后缀
        # TICK周期没有复权概念，不需要后缀
        # 检查远程后复权开关，保持与 api_data_fetcher.py 一致
        try:
            from ..config.trading_config import ENABLE_REMOTE_ADJUST
        except ImportError:
            ENABLE_REMOTE_ADJUST = False
        
        if not ENABLE_REMOTE_ADJUST and adjust_type == '1':
            print(f"[数据记录器] 远程服务器升级中暂不支持后复权，adjust_type 已从 '1' 强制改为 '0'")
            adjust_type = '0'
            self.adjust_type = '0'  # 同步更新实例属性
        
        if kline_period.lower() == 'tick':
            self.kline_suffix = None  # TICK模式不保存K线到DB
        else:
            self.kline_suffix = 'hfq' if adjust_type == '1' else 'raw'
        
        # 初始化后台写入线程（所有记录器共用）
        if save_kline_csv or save_kline_db or save_tick_csv or save_tick_db:
            DataRecorder._init_write_thread()
        
        # 打印配置信息
        print(f"[数据记录器] 初始化 - {symbol}")
        print(f"  K线保存: CSV={'开' if save_kline_csv else '关'}, DB={'开' if save_kline_db else '关'}")
        print(f"  TICK保存: CSV={'开' if save_tick_csv else '关'}, DB={'开' if save_tick_db else '关'}")
        if save_kline_csv or save_tick_csv:
            print(f"  CSV路径: {save_path}")
        if save_kline_db or save_tick_db:
            print(f"  DB路径: {db_path}")
            if save_kline_db and self.kline_suffix:
                print(f"  K线表名: {self.continuous_symbol}_{kline_period.upper()}_{self.kline_suffix}")
            if save_tick_db:
                print(f"  TICK表名: {self.continuous_symbol}_tick")
    
    def record_tick(self, tick_data: Dict):
        """记录TICK数据 - 放入队列异步保存"""
        if not self.save_tick_csv and not self.save_tick_db:
            return
        
        # 构建datetime字段
        trading_day = tick_data.get('TradingDay', '')
        update_time = tick_data.get('UpdateTime', '')
        millisec = tick_data.get('UpdateMillisec', 0)
        
        datetime_str = ''
        if trading_day and update_time:
            datetime_str = f"{trading_day[:4]}-{trading_day[4:6]}-{trading_day[6:]} {update_time}.{millisec:03d}"
        
        # 统一字段顺序：datetime 放在第一位，保持与导入工具一致
        tick_record = {'datetime': datetime_str}
        tick_record.update(tick_data)
        
        # 放入队列异步保存（不阻塞）
        if self.save_tick_csv:
            DataRecorder._write_queue.put(('tick_csv', tick_record.copy(), {'file_path': self.tick_file}))
        
        if self.save_tick_db:
            table_name = f"{self.continuous_symbol}_tick"
            DataRecorder._write_queue.put(('tick_db', tick_record.copy(), {'db_path': self.db_path, 'table_name': table_name}))
    
    def record_kline(self, kline_data: Dict):
        """记录K线数据 - 放入队列异步保存"""
        if not self.save_kline_csv and not self.save_kline_db:
            return
        
        # K线数据字段已经与历史数据格式一致，直接复制
        # 字段: datetime, symbol, open, high, low, close, volume, amount, openint, cumulative_openint
        kline_record = kline_data.copy()
        
        # 放入队列异步保存（不阻塞）
        if self.save_kline_csv:
            DataRecorder._write_queue.put(('kline_csv', kline_record.copy(), {'file_path': self.kline_file}))
        
        if self.save_kline_db and self.kline_suffix:
            # TICK模式下 kline_suffix 为 None，跳过K线DB保存
            # 周期统一用大写（如 1M, 5M），与云端数据格式一致
            table_name = f"{self.continuous_symbol}_{self.kline_period.upper()}_{self.kline_suffix}"
            DataRecorder._write_queue.put(('kline_db', kline_record.copy(), {'db_path': self.db_path, 'table_name': table_name}))
    
    def flush_all(self):
        """等待队列中所有数据写入完成"""
        if DataRecorder._write_queue:
            DataRecorder._write_queue.join()  # 等待队列清空


class LiveDataSource:
    """实盘数据源 - 模拟回测时的DataSource接口"""
    
    def __init__(self, symbol: str, config: Dict):
        """
        初始化实盘数据源
        
        Args:
            symbol: 合约代码
            config: 配置参数
        """
        self.symbol = symbol
        self.config = config
        
        # 持仓信息
        self.current_pos = 0  # 当前持仓 (正数多头，负数空头)
        self.today_pos = 0  # 今仓
        self.yd_pos = 0  # 昨仓
        
        # 多空持仓分离（用于需要单独访问多头和空头持仓的场景）
        self.long_pos = 0  # 多头持仓
        self.short_pos = 0  # 空头持仓
        self.long_today = 0  # 多头今仓
        self.short_today = 0  # 空头今仓
        self.long_yd = 0  # 多头昨仓
        self.short_yd = 0  # 空头昨仓
        self.current_price = 0.0
        self.current_datetime = None
        self.current_idx = 0
        
        # K线数据缓存
        # lookback_bars 控制缓存大小，默认1000，设置0或不设置则使用默认值
        cache_maxlen = config.get('lookback_bars', 0) or 1000
        cache_maxlen = max(cache_maxlen, 100)  # 至少100条
        self.klines = deque(maxlen=cache_maxlen)  # 保存最近的K线
        self.kline_count = 0  # K线总数计数器（不受deque长度限制）
        
        # Tick数据缓存
        # 统一使用 lookback_bars 控制缓存大小
        self.ticks = deque(maxlen=cache_maxlen)  # 保存最近的TICK
        
        # K线聚合状态
        self.kline_period = config.get('kline_period', '1min')  # K线周期
        self.current_kline = None  # 当前正在聚合的K线
        self.last_kline_time = None  # 上一根K线的时间
        
        # 成交量计算（用于计算K线成交量增量）
        self.last_tick_volume = 0  # 上一个tick的累计成交量
        self.kline_start_volume = 0  # 当前K线开始时的累计成交量
        
        # 持仓量计算（用于记录K线持仓量变化）
        self.last_tick_open_interest = 0  # 上一个tick的持仓量
        self.kline_start_open_interest = 0  # 当前K线开始时的持仓量
        
        # 交易记录
        self.trades = []
        self.capital = config.get('initial_capital', 100000)
        self.available = self.capital
        
        # 交易参数
        self.commission = config.get('commission', 0.0001)
        self.margin_rate = config.get('margin_rate', 0.1)
        self.contract_multiplier = config.get('contract_multiplier', 10)
        
        # 委托价格偏移设置（跳数）
        self.price_tick = config.get('price_tick', 1.0)  # 最小变动价位
        self.order_offset_ticks = config.get('order_offset_ticks', 5)  # 委托偏移跳数，默认5跳
        
        # 智能算法交易配置
        self.algo_trading = config.get('algo_trading', False)
        self.order_timeout = config.get('order_timeout', 0)
        self.retry_limit = config.get('retry_limit', 0)
        self.retry_offset_ticks = config.get('retry_offset_ticks', 5)
        self.orders_to_resend = {}  # 待重发订单 {OrderSysID: retry_count}
        
        # CTP客户端引用
        self.ctp_client: Optional[Union['SIMNOWClient', 'RealTradingClient']] = None
        
        # 未成交订单跟踪
        self.pending_orders = {}  # {OrderSysID: order_data}
        
        # 历史数据预加载
        if config.get('preload_history', False):
            self._preload_historical_data(config)
    
    def _preload_historical_data(self, config: Dict):
        """预加载历史数据（支持K线和TICK两种模式）"""
        from ..data.historical_preloader import HistoricalDataPreloader
        
        # 获取数据库路径配置
        db_path = config.get('db_path', 'data_cache/backtest_data.db')
        preloader = HistoricalDataPreloader(db_path=db_path)
        
        # TICK周期：预加载历史TICK数据
        if self.kline_period.lower() == 'tick':
            self._preload_historical_tick(config, preloader)
            return
        
        # K线周期：预加载历史K线数据
        # 获取K线数量配置（默认100根）
        lookback_bars = config.get('history_lookback_bars', 100)
        adjust_type = config.get('adjust_type', '0')
        
        # 检查远程后复权开关，保持与 api_data_fetcher.py 一致
        try:
            from ..config.trading_config import ENABLE_REMOTE_ADJUST
        except ImportError:
            ENABLE_REMOTE_ADJUST = False
        
        if not ENABLE_REMOTE_ADJUST and adjust_type == '1':
            print(f"[预加载] 远程服务器升级中暂不支持后复权，adjust_type 已从 '1' 强制改为 '0'")
            adjust_type = '0'
        
        # 用户自定义历史数据符号（如 rb888 主力或 rb777 次主力）
        history_symbol = config.get('history_symbol', None)
        
        print(f"\n[LiveDataSource] 开始预加载历史K线数据...")
        
        historical_df = preloader.preload(
            self.symbol,
            self.kline_period,
            lookback_bars=lookback_bars,
            adjust_type=adjust_type,
            history_symbol=history_symbol
        )
        
        if not historical_df.empty:
            # 将历史数据加载到klines队列
            for idx, row in historical_df.iterrows():
                kline = {
                    'datetime': idx,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row.get('volume', 0)),
                }
                self.klines.append(kline)
            
            # 初始化K线计数器
            self.kline_count = len(self.klines)
            self.current_idx = self.kline_count - 1
            
            # 【关键修复】初始化 last_kline_time，使 K线 聚合从最后一根历史 K线 时间继续
            # 这样第一个 TICK 来时，系统会正确判断是否需要创建新 K线
            last_kline = self.klines[-1]
            self.last_kline_time = pd.to_datetime(last_kline['datetime'])
            
            print(f"[LiveDataSource] ✅ 已预加载 {len(self.klines)} 根历史K线")
            print(f"[LiveDataSource] 历史数据范围: {historical_df.index[0]} 至 {historical_df.index[-1]}\n")
        else:
            print(f"[LiveDataSource] ⚠️ 未加载到历史K线数据\n")
    
    def _preload_historical_tick(self, config: Dict, preloader):
        """预加载历史TICK数据"""
        # 获取TICK数量配置（默认1000条）
        lookback_count = config.get('history_lookback_bars', 1000)
        # 用户自定义历史数据符号（如 au2602，TICK通常使用具体合约）
        history_symbol = config.get('history_symbol', None)
        
        print(f"\n[LiveDataSource] 开始预加载历史TICK数据...")
        
        historical_df = preloader.preload_tick(
            self.symbol,
            lookback_count=lookback_count,
            history_symbol=history_symbol
        )
        
        if not historical_df.empty:
            # 将历史TICK数据加载到ticks队列
            for idx, row in historical_df.iterrows():
                tick_info = row.to_dict()
                tick_info['datetime'] = idx
                self.ticks.append(tick_info)
            
            # 更新当前价格为最后一个TICK的价格
            last_tick = self.ticks[-1]
            if 'LastPrice' in last_tick:
                self.current_price = float(last_tick['LastPrice'])
            self.current_datetime = pd.to_datetime(last_tick['datetime'])
            
            print(f"[LiveDataSource] ✅ 已预加载 {len(self.ticks)} 条历史TICK")
            print(f"[LiveDataSource] 历史TICK范围: {historical_df.index[0]} 至 {historical_df.index[-1]}")
            print(f"[LiveDataSource] 最新价格: {self.current_price}\n")
        else:
            print(f"[LiveDataSource] ⚠️ 未加载到历史TICK数据")
            print(f"[LiveDataSource] 提示: 请确保数据库中存在对应的TICK数据表")
            print(f"[LiveDataSource]       可通过 save_tick_db=True 采集TICK数据\n")
    
    def _check_order_timeout(self):
        """检查订单超时（智能算法交易）"""
        if not self.algo_trading or self.order_timeout <= 0:
            return
        
        current_time = time.time()
        
        # 遍历所有未成交订单
        # 注意：需要拷贝items()，因为循环中可能删除字典元素
        for order_sys_id, order in list(self.pending_orders.items()):
            # 获取订单插入时间
            # 我们需要确保在记录订单时添加了本地时间戳，因为CTP时间可能不同步
            insert_time = order.get('_local_insert_time')
            if not insert_time:
                # 如果没有本地时间戳，尝试解析CTP时间，或者跳过
                # 如果订单是CTP回报中带的，尝试解析InsertTime
                insert_time_str = order.get('InsertTime', '')
                if insert_time_str:
                    try:
                        # CTP返回的时间格式通常是 HH:MM:SS
                        # 我们需要加上当前日期
                        from datetime import datetime
                        now = datetime.now()
                        order_time = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {insert_time_str}", "%Y-%m-%d %H:%M:%S")
                        insert_time = order_time.timestamp()
                        # 更新本地时间戳，避免重复解析
                        order['_local_insert_time'] = insert_time
                    except:
                        pass
            
            if not insert_time:
                continue
                
            if current_time - insert_time > self.order_timeout:
                print(f"[智能追单] 订单超时撤单: {order_sys_id} 已等待{current_time - insert_time:.1f}秒 (阈值:{self.order_timeout}秒)")
                
                # 标记该订单需要重发
                # 记录重发次数，初始为0
                self.orders_to_resend[order_sys_id] = 0
                
                # 发送撤单请求
                exchange_id = order.get('ExchangeID', 'SHFE')
                if self.ctp_client:
                    self.ctp_client.cancel_order(self.symbol, order_sys_id, exchange_id)

    def update_tick(self, tick_data: Dict) -> Dict:  # type: ignore
        """更新tick数据并聚合K线
        
        Returns:
            Dict 或 None: 如果生成了新K线，返回刚完成的K线；否则返回None
        """
        # 检查订单超时
        self._check_order_timeout()
        
        self.current_price = tick_data['LastPrice']
        
        # 格式化时间（使用TradingDay业务日期 + UpdateTime最后修改时间）
        # 【关键修复】CTP 的 TradingDay 是交易日而非自然日
        # 夜盘 21:00-02:30 的 TradingDay 是下一个交易日
        # 需要正确处理跨自然日的情况，避免时间"倒退"
        trading_day = tick_data['TradingDay']
        update_time = tick_data['UpdateTime']
        millisec = tick_data['UpdateMillisec']
        
        # 解析 update_time 的小时
        hour = int(update_time.split(':')[0])
        
        # 修正日期：将 CTP 的交易日时间转换为自然日时间
        # CTP 的 TradingDay 是交易日（周五夜盘的 TradingDay 是下周一）
        # 我们需要转换为真实的自然日（周五夜盘应该是周五的日期）
        # 
        # 关键认识：
        #   - 09:00-17:00 日盘：TradingDay 等于自然日
        #   - 21:00-23:59 夜盘前半段：TradingDay 是下一个交易日，需要反查
        #   - 00:00-02:30 夜盘后半段（凌晨）：TradingDay 已经是当天，直接用系统日期
        # 
        from datetime import datetime as dt
        
        if 9 <= hour < 17:  # 09:00-17:00 日盘时间
            # 日盘时段，TradingDay 就是自然日
            date_str = f"{trading_day[:4]}-{trading_day[4:6]}-{trading_day[6:]}"
        elif hour >= 21:  # 21:00-23:59 夜盘前半段
            # 使用交易日历反查上一个交易日
            # 例如：周四晚 21:00，TradingDay=周五 → 返回周四
            try:
                from ..data.api_data_fetcher import get_prev_trading_day
                date_str = get_prev_trading_day(trading_day)
            except Exception:
                # 回退方案：使用系统当前日期
                date_str = dt.now().strftime('%Y-%m-%d')
        else:  # 00:00-08:59 凌晨时段（夜盘后半段 + 早盘前）
            # 凌晨夜盘（00:00-02:30）应该使用当前系统日期
            # 因为这时候已经是新的一天了
            date_str = dt.now().strftime('%Y-%m-%d')
        
        datetime_str = f"{date_str} {update_time}.{millisec:03d}"
        self.current_datetime = pd.to_datetime(datetime_str)
        
        # 保存完整的CTP原始数据，只添加datetime字段
        tick_info = tick_data.copy()
        tick_info['datetime'] = self.current_datetime
        
        self.ticks.append(tick_info)
        
        # 聚合K线并返回完成的K线
        return self._aggregate_kline(tick_data)
    
    def get_current_price(self) -> float:
        """获取当前价格"""
        return self.current_price
    
    def get_current_datetime(self):
        """获取当前时间"""
        return self.current_datetime
    
    def get_current_pos(self) -> int:
        """获取当前持仓"""
        return self.current_pos
    
    def _get_kline_timestamp(self, dt: pd.Timestamp) -> pd.Timestamp:
        """根据K线周期获取K线时间戳"""
        import re
        # 解析周期
        period = self.kline_period.lower()
        
        # 匹配分钟周期：1m, 5m, 15m, 30m, 1min, 5min 等
        min_match = re.match(r'^(\d+)(m|min)$', period)
        if min_match:
            minutes = int(min_match.group(1))
            # 向下取整到对应的分钟
            new_minute = (dt.minute // minutes) * minutes
            return dt.replace(minute=new_minute, second=0, microsecond=0)
        
        # 匹配小时周期：1h, 2h, 1hour 等
        hour_match = re.match(r'^(\d+)(h|hour)$', period)
        if hour_match:
            hours = int(hour_match.group(1))
            new_hour = (dt.hour // hours) * hours
            return dt.replace(hour=new_hour, minute=0, second=0, microsecond=0)
        
        # 匹配日线：1d, d, day
        if period in ['1d', 'd', 'day']:
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 默认1分钟
        return dt.replace(second=0, microsecond=0)
    
    def _aggregate_kline(self, tick_data: Dict) -> Dict:  # type: ignore
        """聚合tick数据为K线 - 计算成交量增量和持仓量变化
        
        Returns:
            Dict 或 None: 如果生成了新K线，返回刚完成的K线；否则返回None
        """
        # 确保时间不为None
        if self.current_datetime is None:
            return None  # type: ignore
        
        # 获取当前tick的累计成交量和瞬时持仓量
        current_volume = tick_data.get('Volume', 0)
        current_open_interest = tick_data.get('OpenInterest', 0)
        
        # 获取K线时间戳
        kline_time = self._get_kline_timestamp(self.current_datetime)
        
        # 【关键修复】处理历史数据预加载后的状态不一致问题
        # 预加载只设置了 last_kline_time，但没有设置 current_kline
        # 这会导致以下场景失败：
        #   1. 同一分钟恢复：kline_time == last_kline_time，进入else但current_kline是None
        #   2. 时间回退：kline_time < last_kline_time（异常数据），同上
        # 解决方案：当检测到状态不一致时（有last_kline_time但无current_kline），
        # 无条件重置 last_kline_time，让系统从第一个实盘tick开始创建新K线
        if self.last_kline_time is not None and self.current_kline is None:
            # 只在第一个实盘tick时触发（之后 current_kline 会被设置）
            # 这确保历史数据的 last_kline_time 不会阻止实盘K线的创建
            self.last_kline_time = None
        
        # 判断是否需要生成新K线
        if self.last_kline_time is None or kline_time > self.last_kline_time:
            # 保存上一根完成的K线
            completed_kline = None
            if self.current_kline is not None:
                completed_kline = self.current_kline.copy()
                self.klines.append(completed_kline)
                # 增加K线计数器（不受deque长度限制）
                self.kline_count += 1
                self.current_idx = self.kline_count - 1
            
            # 创建新K线时，记录起始成交量和持仓量
            self.kline_start_volume = current_volume
            self.kline_start_open_interest = current_open_interest
            
            # 创建新K线（字段名与历史数据保持一致）
            self.current_kline = {
                'datetime': kline_time,
                'symbol': self.symbol,  # 具体合约代码
                'open': self.current_price,
                'high': self.current_price,
                'low': self.current_price,
                'close': self.current_price,
                'volume': 0,  # 初始成交量为0，后续累加增量
                'amount': None,  # 成交额（实时数据暂无）
                'openint': 0,  # 持仓量变化（初始为0）
                'cumulative_openint': current_open_interest,  # 累计持仓量
            }
            self.last_kline_time = kline_time
            self.last_tick_volume = current_volume
            self.last_tick_open_interest = current_open_interest
            return completed_kline  # type: ignore
        else:
            # 更新当前K线
            if self.current_kline is not None:
                self.current_kline['high'] = max(self.current_kline['high'], self.current_price)
                self.current_kline['low'] = min(self.current_kline['low'], self.current_price)
                self.current_kline['close'] = self.current_price
                
                # 计算成交量增量（当前累计成交量 - K线开始时的累计成交量）
                volume_delta = current_volume - self.kline_start_volume
                self.current_kline['volume'] = max(0, volume_delta)  # 确保成交量非负
                
                # 更新持仓量（字段名与历史数据保持一致）
                self.current_kline['cumulative_openint'] = current_open_interest
                
                # 计算持仓量变化（当前持仓量 - K线开始时的持仓量）
                openint_change = current_open_interest - self.kline_start_open_interest
                self.current_kline['openint'] = openint_change
                
            self.last_tick_volume = current_volume
            self.last_tick_open_interest = current_open_interest
            return None  # type: ignore
    
    def get_klines(self, window: int = None) -> pd.DataFrame:
        """获取K线数据
        
        Args:
            window: 滑动窗口大小，None或0表示返回所有缓存数据（最多deque maxlen条）
            
        Returns:
            K线数据DataFrame，最多返回window条（从最近往前）
        """
        if not self.klines:
            return pd.DataFrame()
        
        klines_list = list(self.klines)
        
        # 如果指定了窗口大小且大于0，只返回最近的window条
        if window is not None and window > 0:
            klines_list = klines_list[-window:]
        
        return pd.DataFrame(klines_list)
    
    def get_close(self) -> pd.Series:
        """获取收盘价序列"""
        df = self.get_klines()
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['close'])
    
    def get_open(self) -> pd.Series:
        """获取开盘价序列"""
        df = self.get_klines()
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['open'])
    
    def get_high(self) -> pd.Series:
        """获取最高价序列"""
        df = self.get_klines()
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['high'])
    
    def get_low(self) -> pd.Series:
        """获取最低价序列"""
        df = self.get_klines()
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['low'])
    
    def get_volume(self) -> pd.Series:
        """获取成交量序列"""
        df = self.get_klines()
        if df.empty:
            return pd.Series(dtype=float)
        return pd.Series(df['volume'])
    
    def get_tick(self) -> Optional[Dict]:
        """获取当前最新的tick数据"""
        if self.ticks:
            return dict(self.ticks[-1])
        return None
    
    def get_ticks(self, window: int = None) -> pd.DataFrame:
        """获取最近window条tick数据
        
        Args:
            window: 窗口大小，None表示返回所有缓存数据，0也表示不限制
            
        Returns:
            DataFrame: tick数据
        """
        if not self.ticks:
            return pd.DataFrame()
        
        tick_list = list(self.ticks)
        
        # 如果指定了窗口大小且大于0，只返回最近的window条
        if window is not None and window > 0:
            if len(tick_list) > window:
                tick_list = tick_list[-window:]
        
        return pd.DataFrame(tick_list)
    
    def buy(self, volume: int = 1, reason: str = "", log_callback=None, order_type: str = 'bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """买入开仓
        
        Args:
            volume: 交易量
            reason: 交易原因
            log_callback: 日志回调
            order_type: 订单类型
            offset_ticks: 价格偏移tick数，如果不提供则使用配置中的order_offset_ticks
            price: 限价单价格（仅当order_type='limit'时有效）
        """
        if not self.ctp_client:
            if log_callback:
                log_callback("[错误] CTP客户端未初始化")
            return
        
        # 确定委托价格
        if price is not None:
            # 显式指定价格
            limit_price = price
            actual_offset = 0
        elif order_type == 'limit' and price is not None:
            # 指定了limit类型且提供了价格
            limit_price = price
            actual_offset = 0
        else:
            # 使用传入的offset_ticks，如果没有则使用配置中的值
            actual_offset = offset_ticks if offset_ticks is not None else self.order_offset_ticks
            
            # 买入使用卖一价+偏移，确保成交（使用CTP原始字段名）
            tick = self.ticks[-1] if self.ticks else None
            if tick and 'AskPrice1' in tick and tick['AskPrice1'] > 0:
                limit_price = tick['AskPrice1'] + self.price_tick * actual_offset
            else:
                limit_price = self.current_price + self.price_tick * actual_offset
        
        if log_callback:
            from datetime import datetime
            time_str = datetime.now().strftime("%H:%M:%S")
            offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
            log_callback(f"📤 [{time_str}] [买开] {self.symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} 原因={reason}")
        
        # 调用CTP接口下单
        self.ctp_client.buy_open(self.symbol, limit_price, volume)
    
    def sell(self, volume: Optional[int] = None, reason: str = "", log_callback=None, order_type: str = 'bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """卖出平仓（平多头）
        
        支持智能分单：当今仓+昨仓混合时，自动拆分为两个订单
        支持旧合约换月：如果持仓来自旧合约，自动使用旧合约代码平仓
        
        Args:
            volume: 交易量，如果不提供则平所有多头持仓
            reason: 交易原因
            log_callback: 日志回调
            order_type: 订单类型
            offset_ticks: 价格偏移tick数，如果不提供则使用配置中的order_offset_ticks
            price: 限价单价格（仅当order_type='limit'时有效）
        """
        if not self.ctp_client:
            if log_callback:
                log_callback("[错误] CTP客户端未初始化")
            return
        
        # 【关键】检查是否有旧合约持仓需要平仓
        # _old_contract 由持仓同步时设置，表示该数据源的持仓实际来自旧合约
        trade_symbol = getattr(self, '_old_contract', None) or self.symbol
        is_old_contract = (trade_symbol != self.symbol)
        if is_old_contract and log_callback:
            log_callback(f"[换月平仓] 使用旧合约 {trade_symbol} 进行平仓（数据源: {self.symbol}）")
        
        # 获取多头今仓和昨仓（支持锁仓情况）
        long_today = getattr(self, 'long_today', 0)
        long_yd = getattr(self, 'long_yd', 0)
        
        # 如果没有指定数量，平所有多头持仓
        if volume is None:
            volume = long_today + long_yd  # 使用实际多头持仓，而非净持仓
        
        if volume <= 0:
            if log_callback:
                log_callback("[提示] 没有多头持仓，无需平仓")
            return
        
        # 检查总仓位是否足够，不足则自动调整
        total_available = long_today + long_yd
        if volume > total_available:
            if log_callback:
                log_callback(f"[持仓调整] 多头持仓不足: 需要{volume}手，实际{total_available}手 → 自动调整为{total_available}手")
            volume = total_available
            if volume <= 0:
                if log_callback:
                    log_callback("[提示] 没有多头持仓可平")
                return
        
        # 确定委托价格
        if price is not None:
            limit_price = price
            actual_offset = 0
        elif order_type == 'limit' and price is not None:
            limit_price = price
            actual_offset = 0
        else:
            # 使用传入的offset_ticks，如果没有则使用配置中的值
            actual_offset = offset_ticks if offset_ticks is not None else self.order_offset_ticks
            
            # 【关键修复】旧合约换月平仓时，使用更大的偏移量确保成交
            # 因为旧合约没有订阅行情，使用的是新合约价格，可能与旧合约价格有差异
            # 使用100跳偏移量，确保能够成交（换月的目标是尽快平掉旧合约）
            if is_old_contract:
                OLD_CONTRACT_OFFSET_TICKS = 100  # 旧合约平仓使用100跳偏移
                actual_offset = max(actual_offset, OLD_CONTRACT_OFFSET_TICKS)
                if log_callback:
                    log_callback(f"[换月平仓] 旧合约 {trade_symbol} 无行情数据，使用大偏移量 {actual_offset} 跳确保成交")
            
            # 计算委托价格（使用CTP原始字段名）
            tick = self.ticks[-1] if self.ticks else None
            if tick and 'BidPrice1' in tick and tick['BidPrice1'] > 0:
                limit_price = tick['BidPrice1'] - self.price_tick * actual_offset
            else:
                limit_price = self.current_price - self.price_tick * actual_offset
        
        # 智能分单：根据今仓和昨仓数量拆分订单
        if long_today >= volume:
            # 今仓足够，只平今仓
            if log_callback:
                log_callback(f"[平多判断] {trade_symbol} 多头今仓={long_today}, 多头昨仓={long_yd} → 平今仓{volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [卖平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} (今仓) 原因={reason}")
            self.ctp_client.sell_close(trade_symbol, limit_price, volume, close_today=True)
            
        elif long_today > 0:
            # 今仓不足，需要分单：先平今仓，再平昨仓
            close_today_volume = long_today
            close_yd_volume = volume - long_today
            
            if log_callback:
                log_callback(f"[平多判断] {trade_symbol} 多头今仓={long_today}, 多头昨仓={long_yd} → 需分单: 平今{close_today_volume}手 + 平昨{close_yd_volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [卖平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={close_today_volume} (今仓) 原因={reason}")
            
            # 先平今仓
            self.ctp_client.sell_close(trade_symbol, limit_price, close_today_volume, close_today=True)
            
            # 再平昨仓（已在前面检查过总仓位，这里昨仓一定足够）
            if close_yd_volume > 0:
                if log_callback:
                    from datetime import datetime
                    time_str = datetime.now().strftime("%H:%M:%S")
                    offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                    log_callback(f"📤 [{time_str}] [卖平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={close_yd_volume} (昨仓) 原因={reason}")
                self.ctp_client.sell_close(trade_symbol, limit_price, close_yd_volume, close_today=False)
        else:
            # 没有今仓，只平昨仓
            if log_callback:
                log_callback(f"[平多判断] {trade_symbol} 多头今仓={long_today}, 多头昨仓={long_yd} → 平昨仓{volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [卖平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} (昨仓) 原因={reason}")
            self.ctp_client.sell_close(trade_symbol, limit_price, volume, close_today=False)
    
    def sellshort(self, volume: int = 1, reason: str = "", log_callback=None, order_type: str = 'bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """卖出开仓(做空)
        
        Args:
            volume: 交易量
            reason: 交易原因
            log_callback: 日志回调
            order_type: 订单类型
            offset_ticks: 价格偏移tick数，如果不提供则使用配置中的order_offset_ticks
            price: 限价单价格（仅当order_type='limit'时有效）
        """
        if not self.ctp_client:
            if log_callback:
                log_callback("[错误] CTP客户端未初始化")
            return
        
        # 确定委托价格
        if price is not None:
            limit_price = price
            actual_offset = 0
        elif order_type == 'limit' and price is not None:
            limit_price = price
            actual_offset = 0
        else:
            # 使用传入的offset_ticks，如果没有则使用配置中的值
            actual_offset = offset_ticks if offset_ticks is not None else self.order_offset_ticks
            
            # 卖出使用买一价-偏移，确保成交（使用CTP原始字段名）
            tick = self.ticks[-1] if self.ticks else None
            if tick and 'BidPrice1' in tick and tick['BidPrice1'] > 0:
                limit_price = tick['BidPrice1'] - self.price_tick * actual_offset
            else:
                limit_price = self.current_price - self.price_tick * actual_offset
        
        if log_callback:
            from datetime import datetime
            time_str = datetime.now().strftime("%H:%M:%S")
            offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
            log_callback(f"📤 [{time_str}] [卖开] {self.symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} 原因={reason}")
        
        # 调用CTP接口下单
        self.ctp_client.sell_open(self.symbol, limit_price, volume)
    
    def buycover(self, volume: Optional[int] = None, reason: str = "", log_callback=None, order_type: str = 'bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """买入平仓（平空头）
        
        支持智能分单：当今仓+昨仓混合时，自动拆分为两个订单
        支持旧合约换月：如果持仓来自旧合约，自动使用旧合约代码平仓
        
        Args:
            volume: 交易量，如果不提供则平所有空头持仓
            reason: 交易原因
            log_callback: 日志回调
            order_type: 订单类型
            offset_ticks: 价格偏移tick数，如果不提供则使用配置中的order_offset_ticks
            price: 限价单价格（仅当order_type='limit'时有效）
        """
        if not self.ctp_client:
            if log_callback:
                log_callback("[错误] CTP客户端未初始化")
            return
        
        # 【关键】检查是否有旧合约持仓需要平仓
        trade_symbol = getattr(self, '_old_contract', None) or self.symbol
        is_old_contract = (trade_symbol != self.symbol)
        if is_old_contract and log_callback:
            log_callback(f"[换月平仓] 使用旧合约 {trade_symbol} 进行平仓（数据源: {self.symbol}）")
        
        # 获取空头今仓和昨仓（支持锁仓情况）
        short_today = getattr(self, 'short_today', 0)
        short_yd = getattr(self, 'short_yd', 0)
        
        # 如果没有指定数量，平所有空头持仓
        if volume is None:
            volume = short_today + short_yd  # 使用实际空头持仓，而非净持仓
        
        if volume <= 0:
            if log_callback:
                log_callback("[提示] 没有空头持仓，无需平仓")
            return
        
        # 检查总仓位是否足够，不足则自动调整
        total_available = short_today + short_yd
        if volume > total_available:
            if log_callback:
                log_callback(f"[持仓调整] 空头持仓不足: 需要{volume}手，实际{total_available}手 → 自动调整为{total_available}手")
            volume = total_available
            if volume <= 0:
                if log_callback:
                    log_callback("[提示] 没有空头持仓可平")
                return
        
        # 确定委托价格
        if price is not None:
            limit_price = price
            actual_offset = 0
        elif order_type == 'limit' and price is not None:
            limit_price = price
            actual_offset = 0
        else:
            # 使用传入的offset_ticks，如果没有则使用配置中的值
            actual_offset = offset_ticks if offset_ticks is not None else self.order_offset_ticks
            
            # 【关键修复】旧合约换月平仓时，使用更大的偏移量确保成交
            # 因为旧合约没有订阅行情，使用的是新合约价格，可能与旧合约价格有差异
            # 使用100跳偏移量，确保能够成交（换月的目标是尽快平掉旧合约）
            if is_old_contract:
                OLD_CONTRACT_OFFSET_TICKS = 100  # 旧合约平仓使用100跳偏移
                actual_offset = max(actual_offset, OLD_CONTRACT_OFFSET_TICKS)
                if log_callback:
                    log_callback(f"[换月平仓] 旧合约 {trade_symbol} 无行情数据，使用大偏移量 {actual_offset} 跳确保成交")
            
            # 计算委托价格（使用CTP原始字段名）
            tick = self.ticks[-1] if self.ticks else None
            if tick and 'AskPrice1' in tick and tick['AskPrice1'] > 0:
                limit_price = tick['AskPrice1'] + self.price_tick * actual_offset
            else:
                limit_price = self.current_price + self.price_tick * actual_offset
        
        # 智能分单：根据今仓和昨仓数量拆分订单
        if short_today >= volume:
            # 今仓足够，只平今仓
            if log_callback:
                log_callback(f"[平空判断] {trade_symbol} 空头今仓={short_today}, 空头昨仓={short_yd} → 平今仓{volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [买平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} (今仓) 原因={reason}")
            self.ctp_client.buy_close(trade_symbol, limit_price, volume, close_today=True)
            
        elif short_today > 0:
            # 今仓不足，需要分单：先平今仓，再平昨仓
            close_today_volume = short_today
            close_yd_volume = volume - short_today
            
            if log_callback:
                log_callback(f"[平空判断] {trade_symbol} 空头今仓={short_today}, 空头昨仓={short_yd} → 需分单: 平今{close_today_volume}手 + 平昨{close_yd_volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [买平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={close_today_volume} (今仓) 原因={reason}")
            
            # 先平今仓
            self.ctp_client.buy_close(trade_symbol, limit_price, close_today_volume, close_today=True)
            
            # 再平昨仓（已在前面检查过总仓位，这里昨仓一定足够）
            if close_yd_volume > 0:
                if log_callback:
                    from datetime import datetime
                    time_str = datetime.now().strftime("%H:%M:%S")
                    offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                    log_callback(f"📤 [{time_str}] [买平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={close_yd_volume} (昨仓) 原因={reason}")
                self.ctp_client.buy_close(trade_symbol, limit_price, close_yd_volume, close_today=False)
        else:
            # 没有今仓，只平昨仓
            if log_callback:
                log_callback(f"[平空判断] {trade_symbol} 空头今仓={short_today}, 空头昨仓={short_yd} → 平昨仓{volume}手")
                from datetime import datetime
                time_str = datetime.now().strftime("%H:%M:%S")
                offset_msg = f"(偏移{actual_offset}跳)" if actual_offset != 0 else "(限价)"
                log_callback(f"📤 [{time_str}] [买平] {trade_symbol} 委托价={limit_price:.2f} {offset_msg} 数量={volume} (昨仓) 原因={reason}")
            self.ctp_client.buy_close(trade_symbol, limit_price, volume, close_today=False)
    
    def buytocover(self, volume: Optional[int] = None, reason: str = "", log_callback=None, order_type: str = 'bar_close', offset_ticks: Optional[int] = None, price: Optional[float] = None):
        """买入平仓(平空) - 别名
        
        Args:
            volume: 交易量，如果不提供则平所有空头持仓
            reason: 交易原因
            log_callback: 日志回调
            order_type: 订单类型
            offset_ticks: 价格偏移tick数，如果不提供则使用配置中的order_offset_ticks
            price: 限价单价格（仅当order_type='limit'时有效）
        """
        return self.buycover(volume, reason, log_callback, order_type, offset_ticks, price)
    
    def close_all(self, reason: str = "", log_callback=None, order_type: str = 'bar_close'):
        """平掉所有持仓（包括锁仓情况）"""
        # 获取多头和空头的实际持仓（不是净持仓）
        long_pos = getattr(self, 'long_today', 0) + getattr(self, 'long_yd', 0)
        short_pos = getattr(self, 'short_today', 0) + getattr(self, 'short_yd', 0)
        
        # 平掉多头持仓
        if long_pos > 0:
            if log_callback:
                log_callback(f"[close_all] {self.symbol} 平多头持仓 {long_pos} 手")
            self.sell(volume=long_pos, reason=reason, log_callback=log_callback, order_type=order_type)
        
        # 平掉空头持仓
        if short_pos > 0:
            if log_callback:
                log_callback(f"[close_all] {self.symbol} 平空头持仓 {short_pos} 手")
            self.buycover(volume=short_pos, reason=reason, log_callback=log_callback, order_type=order_type)
    
    def reverse_pos(self, reason: str = "", log_callback=None, order_type: str = 'bar_close'):
        """反转持仓"""
        # 先记录原持仓方向（平仓后 current_pos 会变成 0）
        long_pos = getattr(self, 'long_today', 0) + getattr(self, 'long_yd', 0)
        short_pos = getattr(self, 'short_today', 0) + getattr(self, 'short_yd', 0)
        was_long = long_pos > 0
        was_short = short_pos > 0
        
        # 先平仓
        self.close_all(reason=reason, log_callback=log_callback, order_type=order_type)
        
        # 再反向开仓
        time.sleep(0.5)  # 等待平仓完成
        
        if was_long and not was_short:
            # 原来是多头，反转为空头
            self.sellshort(volume=1, reason=reason, log_callback=log_callback, order_type=order_type)
        elif was_short and not was_long:
            # 原来是空头，反转为多头
            self.buy(volume=1, reason=reason, log_callback=log_callback, order_type=order_type)
        elif was_long and was_short:
            # 锁仓情况，不做反转（避免复杂情况）
            if log_callback:
                log_callback(f"[reverse_pos] {self.symbol} 存在锁仓（多{long_pos}空{short_pos}），仅平仓不反转")
    
    def cancel_all_orders(self, log_callback=None):
        """
        撤销所有未成交的订单
        
        注意：需要订单系统编号(OrderSysID)才能撤单
        """
        if not self.ctp_client:
            if log_callback:
                log_callback("[错误] CTP客户端未初始化")
            return
        
        if not hasattr(self, 'pending_orders') or not self.pending_orders:
            if log_callback:
                log_callback(f"[撤单] {self.symbol} 无未成交订单")
            return
        
        # 撤销所有未成交的订单
        cancel_count = 0
        for order in list(self.pending_orders.values()):
            if order.get('OrderSysID') and order.get('OrderStatus') in ['1', '3', 'a']:  # 部分成交/未成交/未知
                # 从订单数据中获取交易所代码
                exchange_id = order.get('ExchangeID', 'SHFE')  # 如果没有则默认上期所
                
                if log_callback:
                    log_callback(f"[撤单] {self.symbol} 订单号={order['OrderSysID']} 交易所={exchange_id}")
                
                self.ctp_client.cancel_order(self.symbol, order['OrderSysID'], exchange_id)
                cancel_count += 1
        
        if cancel_count > 0 and log_callback:
            log_callback(f"[撤单] 共撤销 {cancel_count} 个订单")
        
        # 等待撤单完成
        if cancel_count > 0:
            time.sleep(0.3)


class MultiDataSource:
    """多数据源容器 - 兼容回测API"""
    
    def __init__(self, data_sources: List[LiveDataSource]):
        self.data_sources = data_sources
    
    def __getitem__(self, index: int) -> LiveDataSource:
        return self.data_sources[index]
    
    def __len__(self) -> int:
        return len(self.data_sources)


class LiveTradingAdapter:
    """实盘交易适配器"""
    
    def __init__(self, mode: str, config: Dict, strategy_func: Callable, 
                 initialize_func: Optional[Callable] = None,
                 strategy_params: Optional[Dict] = None,
                 on_trade_callback: Optional[Callable] = None,
                 on_order_callback: Optional[Callable] = None,
                 on_cancel_callback: Optional[Callable] = None,
                 on_order_error_callback: Optional[Callable] = None,
                 on_cancel_error_callback: Optional[Callable] = None,
                 on_account_callback: Optional[Callable] = None,
                 on_position_callback: Optional[Callable] = None,
                 on_position_complete_callback: Optional[Callable] = None,
                 on_disconnect_callback: Optional[Callable] = None,
                 on_query_trade_callback: Optional[Callable] = None,
                 on_query_trade_complete_callback: Optional[Callable] = None):
        """
        初始化实盘交易适配器
        
        Args:
            mode: 'simnow' 或 'real'
            config: 配置字典
            strategy_func: 策略函数
            initialize_func: 初始化函数
            strategy_params: 策略参数
            on_trade_callback: 用户自定义成交回调
            on_order_callback: 用户自定义报单回调
            on_cancel_callback: 用户自定义撤单回调
            on_order_error_callback: 用户自定义报单错误回调
            on_cancel_error_callback: 用户自定义撤单错误回调
            on_account_callback: 用户自定义账户资金回调
            on_position_callback: 用户自定义持仓回调
            on_position_complete_callback: 用户自定义持仓查询完成回调
            on_disconnect_callback: 用户自定义断开连接回调
            on_query_trade_callback: 用户自定义成交查询回调（单条）
            on_query_trade_complete_callback: 用户自定义成交查询完成回调
        """
        self.mode = mode
        self.config = config
        self.strategy_func = strategy_func
        self.initialize_func = initialize_func
        self.strategy_params = strategy_params or {}
        self.on_trade_callback = on_trade_callback
        self.on_order_callback = on_order_callback
        self.on_cancel_callback = on_cancel_callback
        self.on_order_error_callback = on_order_error_callback
        self.on_cancel_error_callback = on_cancel_error_callback
        self.on_account_callback = on_account_callback
        self.on_position_callback = on_position_callback
        self.on_position_complete_callback = on_position_complete_callback
        self.on_disconnect_callback = on_disconnect_callback
        self.on_query_trade_callback = on_query_trade_callback
        self.on_query_trade_complete_callback = on_query_trade_complete_callback
        
        # CTP客户端
        self.ctp_client: Optional[Union['SIMNOWClient', 'RealTradingClient']] = None
        
        # 账户信息（实时更新）
        self.account_info = {
            'balance': 0,           # 账户权益
            'available': 0,         # 可用资金
            'position_profit': 0,   # 持仓盈亏
            'close_profit': 0,      # 平仓盈亏
            'commission': 0,        # 手续费
            'frozen_margin': 0,     # 冻结保证金
            'curr_margin': 0,       # 占用保证金
            'update_time': None,    # 更新时间
        }
        
        # 数据源
        self.data_source: Optional[LiveDataSource] = None
        self.multi_data_source: Optional[MultiDataSource] = None
        
        # 持仓查询完成事件
        import threading
        self._position_query_done = threading.Event()
        
        # 策略API
        self.api = None
        
        # 数据记录器 - 为每个数据源（品种+周期）创建独立的记录器
        # 键格式: {symbol}_{kline_period}，如 rb2601_1m, rb2601_5m
        self.data_recorders = {}
        save_kline_csv = config.get('save_kline_csv', False)
        save_kline_db = config.get('save_kline_db', False)
        save_tick_csv = config.get('save_tick_csv', False)
        save_tick_db = config.get('save_tick_db', False)
        
        if save_kline_csv or save_kline_db or save_tick_csv or save_tick_db:
            save_path = config.get('data_save_path', './live_data')
            db_path = config.get('db_path', 'data_cache/backtest_data.db')
            
            # 支持单数据源和多数据源
            if 'data_sources' in config:
                # 多数据源模式：为每个数据源创建记录器（支持同品种不同周期）
                for ds_config in config['data_sources']:
                    symbol = ds_config['symbol']
                    kline_period = ds_config.get('kline_period', '1m')
                    adjust_type = ds_config.get('adjust_type', '0')
                    
                    # 键: symbol_period，支持同品种多周期
                    recorder_key = f"{symbol}_{kline_period}"
                    self.data_recorders[recorder_key] = DataRecorder(
                        symbol=symbol,
                        kline_period=kline_period,
                        save_path=save_path,
                        db_path=db_path,
                        save_kline_csv=save_kline_csv,
                        save_kline_db=save_kline_db,
                        save_tick_csv=save_tick_csv,
                        save_tick_db=save_tick_db,
                        adjust_type=adjust_type,
                    )
            else:
                # 单数据源模式
                symbol = config['symbol']
                kline_period = config.get('kline_period', '1m')
                adjust_type = config.get('adjust_type', '0')
                
                recorder_key = f"{symbol}_{kline_period}"
                self.data_recorders[recorder_key] = DataRecorder(
                    symbol=symbol,
                    kline_period=kline_period,
                    save_path=save_path,
                    db_path=db_path,
                    save_kline_csv=save_kline_csv,
                    save_kline_db=save_kline_db,
                    save_tick_csv=save_tick_csv,
                    save_tick_db=save_tick_db,
                    adjust_type=adjust_type,
                )
        
        # 运行标志
        self.running = False
        self.strategy_thread = None
        
        # TICK流支持（双驱动模式）
        self.enable_tick_callback = config.get('enable_tick_callback', False)
        
        print(f"[实盘适配器] 初始化 - 模式: {mode}")
        if self.enable_tick_callback:
            print(f"[实盘适配器] ✓ TICK流双驱动模式已启用（每个tick和K线完成时都会触发策略）")
    
    def run(self) -> Dict[str, Any]:
        """运行实盘交易"""
        # 初始化CTP客户端
        self._init_ctp_client()
        
        # 初始化数据源
        self._init_data_source()
        
        # 创建策略API
        self._create_strategy_api()
        
        # 运行策略初始化
        if self.initialize_func:
            print("[实盘适配器] 运行策略初始化...")
            self.initialize_func(self.api)
        
        # 连接CTP
        print("[实盘适配器] 连接CTP服务器...")
        if self.ctp_client:
            self.ctp_client.connect()
            
            # 等待连接就绪
            self.ctp_client.wait_ready(timeout=30)
            
            # 查询持仓（同步到本地状态）
            # 重置持仓查询完成事件
            self._position_query_done.clear()
            
            # 清除旧的持仓缓存（使用覆盖模式，每次查询开始时清空）
            self._position_cache = {}
            
            # 【修复】使用空字符串查询所有持仓，避免大小写不匹配导致查不到
            # CTP 的 ReqQryInvestorPosition 传空字符串会返回账户所有持仓
            self._pending_position_queries = set([''])  # 只查询一次
            self.ctp_client.query_position('')  # 空字符串 = 查询所有持仓
            
            # 等待持仓查询完成（事件驱动，最多等待10秒）
            self._position_query_done.wait(timeout=10)
        else:
            raise RuntimeError("CTP客户端初始化失败")
        
        # 启动策略线程
        self.running = True
        
        # 品牌与免责声明（在CTP连接就绪后显示）
        self._print_disclaimer()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[实盘适配器] 用户中断")
        finally:
            self.stop()
        
        # 返回结果
        result = {
            'status': 'completed',
            'mode': self.mode,
        }
        
        # 添加symbol信息
        if 'data_sources' in self.config:
            result['symbols'] = [ds['symbol'] for ds in self.config['data_sources']]
        else:
            result['symbol'] = self.config['symbol']
        
        return result
    
    def _print_disclaimer(self):
        """打印品牌信息与免责声明"""
        border = "=" * 80
        print(f"\n{border}")
        print("  🐿️  松鼠Quant (SSQuant) - 专业量化交易框架")
        print(f"{border}")
        print("  🌐 官方网站: quant789.com")
        print("  📱 公众号  : 松鼠Quant")
        print(f"{border}")
        print("  ⚠️  风险提示 & 免责声明:")
        print("  1. 期货交易具有高风险，可能导致本金全部损失。")
        print("  2. 本软件仅供学习、研究与策略开发使用，不构成任何投资建议，且不能保证框架无BUG。")
        print("  3. 历史回测业绩不代表未来表现，模拟盘盈利不代表实盘盈利。")
        print("  4. 使用本软件产生的任何交易盈亏由用户自行承担，开发者不承担任何责任。")
        print("  5. 若不同意以上条款，请立即停止使用并退出！")
        print(f"{border}\n")

    def _init_ctp_client(self) -> None:
        """初始化CTP客户端"""
        # 获取订阅列表
        if 'data_sources' in self.config:
            # 多数据源模式：订阅所有品种（去重）
            subscribe_list = list(set([ds['symbol'] for ds in self.config['data_sources']]))
            print(f"[CTP客户端] 多数据源模式，准备订阅 {len(subscribe_list)} 个品种:")
            for symbol in subscribe_list:
                print(f"  - {symbol}")
        else:
            # 单数据源模式
            subscribe_list = [self.config['symbol']]
            print(f"[CTP客户端] 单数据源模式，订阅品种: {subscribe_list[0]}")
        
        if self.mode == 'simnow':
            from ..pyctp.simnow_client import SIMNOWClient
            
            self.ctp_client = SIMNOWClient(
                investor_id=self.config['investor_id'],
                password=self.config['password'],
                server_name=self.config.get('server_name', '24hour'),
                subscribe_list=subscribe_list
            )
        
        elif self.mode == 'real':
            from ..pyctp.real_trading_client import RealTradingClient
            
            self.ctp_client = RealTradingClient(
                broker_id=self.config['broker_id'],
                investor_id=self.config['investor_id'],
                password=self.config['password'],
                md_server=self.config['md_server'],
                td_server=self.config['td_server'],
                app_id=self.config['app_id'],
                auth_code=self.config['auth_code'],
                subscribe_list=subscribe_list
            )
        
        # 设置回调
        if self.ctp_client:
            self.ctp_client.on_market_data = self._on_market_data
            self.ctp_client.on_trade = self._on_trade
            self.ctp_client.on_order = self._on_order
            self.ctp_client.on_cancel = self._on_cancel
            self.ctp_client.on_position = self._on_position
            self.ctp_client.on_position_complete = self._on_position_complete
            self.ctp_client.on_order_error = self._on_order_error
            self.ctp_client.on_cancel_error = self._on_cancel_error
            self.ctp_client.on_account = self._on_account
            self.ctp_client.on_disconnected = self._on_disconnect
            self.ctp_client.on_query_trade = self._on_query_trade
            self.ctp_client.on_query_trade_complete = self._on_query_trade_complete
    
    def _init_data_source(self):
        """初始化数据源"""
        data_sources = []
        
        if 'data_sources' in self.config:
            # 多数据源模式
            for ds_config in self.config['data_sources']:
                # 合并配置：优先使用数据源独立配置，再用全局配置
                merged_config = {
                    **self.config,  # 全局配置
                    **ds_config,    # 数据源独立配置（会覆盖全局配置）
                }
                # 确保 kline_period 正确设置
                merged_config['kline_period'] = ds_config.get('kline_period', self.config.get('kline_period', '1min'))
                
                data_source = LiveDataSource(
                    symbol=ds_config['symbol'],
                    config=merged_config
                )
                data_source.ctp_client = self.ctp_client
                data_sources.append(data_source)
            
            # 第一个数据源作为主数据源
            self.data_source = data_sources[0]
        else:
            # 单数据源模式
            self.data_source = LiveDataSource(
                symbol=self.config['symbol'],
                config=self.config
            )
            self.data_source.ctp_client = self.ctp_client
            data_sources.append(self.data_source)
        
        # 创建多数据源容器(兼容回测API)
        self.multi_data_source = MultiDataSource(data_sources)
    
    def _create_strategy_api(self):
        """创建策略API"""
        context = {
            'data': self.multi_data_source,
            'log': self._log,
            'params': self.strategy_params,
            'account_info': self.account_info,  # 账户信息引用
            'ctp_client': self.ctp_client,      # CTP客户端引用
        }
        
        from ..api.strategy_api import create_strategy_api
        self.api = create_strategy_api(context)
    
    def _on_market_data(self, data: Dict):
        """行情回调 - 支持TICK流双驱动模式"""
        # 获取合约代码
        symbol = data.get('InstrumentID', '')
        
        # 找到对应的数据源并更新（同一品种可能有多个周期的数据源）
        completed_kline = None
        target_data_source = None
        completed_klines = []  # 存储所有周期完成的K线
        
        for ds in self.multi_data_source.data_sources:
            # 使用大小写不敏感的匹配（CTP返回的合约代码可能与订阅时大小写不同）
            if ds.symbol.upper() == symbol.upper():
                kline = ds.update_tick(data)
                # 记录每个周期完成的K线（用于数据保存）
                if kline is not None:
                    completed_klines.append((ds, kline))
                    # 记录第一个完成K线的数据源（用于触发策略）
                    if completed_kline is None:
                        completed_kline = kline
                        target_data_source = ds
                elif target_data_source is None:
                    target_data_source = ds
                # 不break，继续更新同品种的其他周期数据源
        
        # 【关键修复】保存当前TICK数据，让策略能通过 api.get_tick() 获取
        # 在多数据源模式下，这样可以获取到"触发策略的那个TICK"
        if target_data_source:
            self.multi_data_source._current_tick = data
            self.multi_data_source._current_tick_symbol = symbol
        
        # 记录数据
        if target_data_source:
            # TICK记录：同一品种只用第一个记录器记录（避免多周期重复）
            # 初始化品种->记录器的映射（只在第一次时建立，大小写不敏感）
            if not hasattr(self, '_symbol_tick_recorder'):
                self._symbol_tick_recorder = {}
                for key, recorder in self.data_recorders.items():
                    sym = key.rsplit('_', 1)[0]  # 从 rb2601_1m 提取 rb2601
                    sym_upper = sym.upper()
                    if sym_upper not in self._symbol_tick_recorder:
                        self._symbol_tick_recorder[sym_upper] = recorder
            
            # 用该品种对应的记录器记录 TICK（大小写不敏感）
            symbol_upper = symbol.upper()
            if symbol_upper in self._symbol_tick_recorder:
                self._symbol_tick_recorder[symbol_upper].record_tick(data)
            
            # K线记录：每个周期独立记录（修复：记录所有周期完成的K线）
            # 使用数据源自身的 symbol（保持原始大小写）
            for ds, kline in completed_klines:
                recorder_key = f"{ds.symbol}_{ds.kline_period}"
                if recorder_key in self.data_recorders:
                    self.data_recorders[recorder_key].record_kline(kline)
        
        if not self.running:
            return
        
        # 双驱动模式：TICK流 + K线完成
        try:
            # 1. TICK级回调（如果启用）
            if self.enable_tick_callback:
                # 每个tick都执行策略（高频模式）
                self.strategy_func(self.api)
            
            # 2. K线完成时回调（始终触发）
            if completed_kline is not None:
                # 如果没有启用TICK流，则在K线完成时执行策略
                if not self.enable_tick_callback:
                    self.strategy_func(self.api)
        except Exception as e:
            print(f"[策略执行错误] {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 【清理】策略执行完成后，清除当前TICK引用
            if hasattr(self.multi_data_source, '_current_tick'):
                delattr(self.multi_data_source, '_current_tick')
            if hasattr(self.multi_data_source, '_current_tick_symbol'):
                delattr(self.multi_data_source, '_current_tick_symbol')
    
    def _on_trade(self, data: Dict):
        """成交回调"""
        # 方向映射
        direction = '买' if data['Direction'] == '0' else '卖'
        
        # 开平映射
        offset_flag = data.get('OffsetFlag', '0')
        offset_map = {
            '0': '开仓',
            '1': '平仓',
            '3': '平今',
            '4': '平昨',
        }
        offset = offset_map.get(offset_flag, '开仓')
        
        symbol = data['InstrumentID']
        
        # 时间（CTP返回的格式是 HH:MM:SS，已带冒号）
        trade_time = data.get('TradeTime', '')
        # 如果已经包含冒号，直接使用；否则按 HHMMSS 格式处理
        if ':' in trade_time:
            time_str = trade_time
        elif trade_time and len(trade_time) >= 6:
            time_str = f"{trade_time[:2]}:{trade_time[2:4]}:{trade_time[4:6]}"
        else:
            time_str = trade_time
        
        print(f"\n✅ [成交] {time_str} {symbol} {direction}{offset} "
              f"价格={data['Price']:.2f} 数量={data['Volume']}")
        
        # 更新持仓：找到对应的数据源
        # 支持旧合约成交：如果数据源的 _old_contract 与成交合约匹配，也进行更新
        for ds in self.multi_data_source.data_sources:
            # 精确匹配或旧合约匹配
            old_contract = getattr(ds, '_old_contract', None)
            is_match = (ds.symbol == symbol) or (old_contract and old_contract.upper() == symbol.upper())
            if is_match:
                volume = data['Volume']
                direction_flag = data['Direction']
                
                # 【调试】记录成交前的持仓
                old_current_pos = ds.current_pos
                old_today_pos = ds.today_pos
                old_yd_pos = ds.yd_pos
                
                # 初始化多空持仓（如果不存在）
                if not hasattr(ds, 'long_pos'):
                    ds.long_pos = 0
                    ds.short_pos = 0
                    ds.long_today = 0
                    ds.short_today = 0
                    ds.long_yd = 0
                    ds.short_yd = 0
                
                # 根据开平方向更新持仓
                if offset_flag == '0':  # 开仓
                    if direction_flag == '0':  # 买开
                        ds.current_pos += volume
                        ds.today_pos += volume  # 增加今仓（多头）
                        # 同步更新多空持仓
                        ds.long_pos += volume
                        ds.long_today += volume
                    else:  # 卖开
                        ds.current_pos -= volume
                        ds.today_pos -= volume  # 增加今仓（空头，负数）
                        # 同步更新多空持仓
                        ds.short_pos += volume
                        ds.short_today += volume
                        
                elif offset_flag == '3':  # 平今
                    if direction_flag == '0':  # 买平（平空头今仓）
                        ds.current_pos += volume
                        ds.today_pos += volume  # 空头今仓是负数，加volume就是减少绝对值
                        # 同步更新多空持仓
                        ds.short_pos = max(0, ds.short_pos - volume)
                        ds.short_today = max(0, ds.short_today - volume)
                    else:  # 卖平（平多头今仓）
                        ds.current_pos -= volume
                        ds.today_pos -= volume  # 多头今仓是正数，减volume
                        # 同步更新多空持仓
                        ds.long_pos = max(0, ds.long_pos - volume)
                        ds.long_today = max(0, ds.long_today - volume)
                        
                elif offset_flag == '4':  # 平昨
                    if direction_flag == '0':  # 买平（平空头昨仓）
                        ds.current_pos += volume
                        ds.yd_pos += volume  # 空头昨仓是负数，加volume就是减少绝对值
                        # 同步更新多空持仓
                        ds.short_pos = max(0, ds.short_pos - volume)
                        ds.short_yd = max(0, ds.short_yd - volume)
                    else:  # 卖平（平多头昨仓）
                        ds.current_pos -= volume
                        ds.yd_pos -= volume  # 多头昨仓是正数，减volume
                        # 同步更新多空持仓
                        ds.long_pos = max(0, ds.long_pos - volume)
                        ds.long_yd = max(0, ds.long_yd - volume)
                        
                elif offset_flag == '1':  # 平仓（需要判断是今仓还是昨仓）
                    # 更新净持仓
                    if direction_flag == '0':  # 买平
                        ds.current_pos += volume
                    else:  # 卖平
                        ds.current_pos -= volume
                    
                    # 判断平的是今仓还是昨仓（使用 short_today/long_today 而不是 today_pos）
                    if direction_flag == '0':  # 买平（平空头）
                        # 使用空头今仓判断（不是净今仓）
                        if ds.short_today > 0:
                            # 优先平今仓
                            reduce_volume = min(volume, ds.short_today)
                            ds.today_pos += reduce_volume  # 净今仓：空头减少 = 加
                            ds.short_today = max(0, ds.short_today - reduce_volume)
                            if volume > reduce_volume:
                                # 今仓不足，平昨仓
                                ds.yd_pos += (volume - reduce_volume)
                                ds.short_yd = max(0, ds.short_yd - (volume - reduce_volume))
                        else:
                            # 没有空头今仓，平昨仓
                            ds.yd_pos += volume
                            ds.short_yd = max(0, ds.short_yd - volume)
                        ds.short_pos = max(0, ds.short_pos - volume)
                    else:  # 卖平（平多头）
                        # 使用多头今仓判断（不是净今仓）
                        if ds.long_today > 0:
                            # 优先平今仓
                            reduce_volume = min(volume, ds.long_today)
                            ds.today_pos -= reduce_volume  # 净今仓：多头减少 = 减
                            ds.long_today = max(0, ds.long_today - reduce_volume)
                            if volume > reduce_volume:
                                # 今仓不足，平昨仓
                                ds.yd_pos -= (volume - reduce_volume)
                                ds.long_yd = max(0, ds.long_yd - (volume - reduce_volume))
                        else:
                            # 没有多头今仓，平昨仓
                            ds.yd_pos -= volume
                            ds.long_yd = max(0, ds.long_yd - volume)
                        ds.long_pos = max(0, ds.long_pos - volume)
                
                # 【关键】平仓成交后，检查是否已平完旧合约持仓
                # 如果已经没有持仓了，清除 _old_contract 标记
                if offset_flag != '0':  # 平仓操作
                    total_pos = getattr(ds, 'long_pos', 0) + getattr(ds, 'short_pos', 0)
                    if total_pos == 0 and hasattr(ds, '_old_contract'):
                        old_contract = ds._old_contract
                        del ds._old_contract
                        print(f"[换月平仓完成] {old_contract} 持仓已清空，已清除旧合约标记")
                
                break
        
        # 调用用户自定义的成交回调
        if self.on_trade_callback:
            try:
                self.on_trade_callback(data)
            except Exception as e:
                print(f"[用户成交回调错误] {e}")
    
    def _on_query_trade(self, data: Dict):
        """成交查询回调（单条记录）"""
        # 调用用户自定义的成交查询回调
        if self.on_query_trade_callback:
            try:
                self.on_query_trade_callback(data)
            except Exception as e:
                print(f"[用户成交查询回调错误] {e}")
    
    def _on_query_trade_complete(self):
        """成交查询完成回调"""
        if self.on_query_trade_complete_callback:
            try:
                self.on_query_trade_complete_callback()
            except Exception as e:
                print(f"[用户成交查询完成回调错误] {e}")
    
    def _on_order(self, data: Dict):
        """报单回调"""
        # 状态映射
        status_map = {
            '0': '全部成交',
            '1': '部分成交还在队列中',
            '3': '未成交还在队列中',
            '5': '撤单',
        }
        status = status_map.get(data['OrderStatus'], f"未知({data['OrderStatus']})")
        
        # 方向映射
        direction_map = {
            '0': '买',
            '1': '卖',
        }
        direction = direction_map.get(data.get('Direction', ''), '未知')
        
        # 开平映射
        offset_flag = data.get('CombOffsetFlag', '0')
        if offset_flag:
            offset_map = {
                '0': '开仓',
                '1': '平仓',
                '3': '平今',
                '4': '平昨',
            }
            offset = offset_map.get(offset_flag[0] if offset_flag else '0', '未知')
        else:
            offset = '开仓'
        
        # 时间（CTP返回的格式是 HH:MM:SS，已带冒号）
        insert_time = data.get('InsertTime', '')
        # 如果已经包含冒号，直接使用；否则按 HHMMSS 格式处理
        if ':' in insert_time:
            time_str = insert_time
        elif insert_time and len(insert_time) >= 6:
            time_str = f"{insert_time[:2]}:{insert_time[2:4]}:{insert_time[4:6]}"
        else:
            time_str = insert_time
        
        # 价格和数量
        price = data.get('LimitPrice', 0)
        volume_original = data.get('VolumeTotalOriginal', 0)
        volume_traded = data.get('VolumeTraded', 0)
        
        print(f"[报单] {time_str} {data['InstrumentID']} {direction}{offset} "
              f"价格={price:.2f} 数量={volume_original} 已成交={volume_traded} 状态={status}")
        
        # 更新未成交订单跟踪
        symbol = data['InstrumentID']
        order_sys_id = data.get('OrderSysID', '')
        order_status = data['OrderStatus']
        
        # 找到对应的数据源并更新pending_orders
        for ds in self.multi_data_source.data_sources:
            if ds.symbol == symbol:
                if order_sys_id:
                    # 如果订单全部成交或撤单，从pending_orders中删除
                    if order_status in ['0', '5']:  # 全部成交或撤单
                        if order_sys_id in ds.pending_orders:
                            del ds.pending_orders[order_sys_id]
                    # 如果是部分成交或未成交，添加/更新到pending_orders
                    elif order_status in ['1', '3', 'a']:  # 部分成交/未成交/未知
                        # 只有当订单不在列表中时才添加本地时间戳（避免更新时覆盖）
                        if order_sys_id not in ds.pending_orders:
                            data['_local_insert_time'] = time.time()
                            
                            # 【智能追单】检查是否有待继承的重试次数
                            if hasattr(ds, '_next_order_retry_count') and ds._next_order_retry_count > 0:
                                ds.orders_to_resend[order_sys_id] = ds._next_order_retry_count
                                # 使用后清除，防止污染其他订单
                                ds._next_order_retry_count = 0
                                print(f"[智能追单] 订单 {order_sys_id} 已继承重试次数: {ds.orders_to_resend[order_sys_id]}")
                        else:
                            # 保留原有的时间戳
                            data['_local_insert_time'] = ds.pending_orders[order_sys_id].get('_local_insert_time', time.time())
                        ds.pending_orders[order_sys_id] = data
                break
        
        # 调用用户自定义的报单回调
        if self.on_order_callback:
            try:
                self.on_order_callback(data)
            except Exception as e:
                print(f"[用户报单回调错误] {e}")
    
    def _on_cancel(self, data: Dict):
        """撤单回调"""
        # 方向映射
        direction_map = {
            '0': '买',
            '1': '卖',
        }
        direction = direction_map.get(data.get('Direction', ''), '未知')
        
        # 开平映射
        offset_flag = data.get('CombOffsetFlag', '0')
        if offset_flag:
            offset_map = {
                '0': '开仓',
                '1': '平仓',
                '3': '平今',
                '4': '平昨',
            }
            offset = offset_map.get(offset_flag[0] if offset_flag else '0', '未知')
        else:
            offset = '开仓'
        
        symbol = data['InstrumentID']
        price = data.get('LimitPrice', 0)
        volume_original = data.get('VolumeTotalOriginal', 0)
        volume_traded = data.get('VolumeTraded', 0)
        order_sys_id = data.get('OrderSysID', '')
        
        # 时间（CTP返回的格式是 HH:MM:SS，已带冒号）
        cancel_time = data.get('CancelTime', '')
        # 如果已经包含冒号，直接使用；否则按 HHMMSS 格式处理
        if ':' in cancel_time:
            time_str = cancel_time
        elif cancel_time and len(cancel_time) >= 6:
            time_str = f"{cancel_time[:2]}:{cancel_time[2:4]}:{cancel_time[4:6]}"
        else:
            time_str = cancel_time
        
        print(f"\n🚫 [撤单成功] {time_str} {symbol} {direction}{offset} "
              f"价格={price:.2f} 数量={volume_original} 已成交={volume_traded} 订单号={order_sys_id}")
        
        # 智能追单逻辑
        for ds in self.multi_data_source.data_sources:
            if ds.symbol == symbol and order_sys_id in ds.orders_to_resend:
                retry_count = ds.orders_to_resend.pop(order_sys_id)
                
                if retry_count < ds.retry_limit:
                    print(f"[智能追单] 触发重发: 剩余重试次数 {ds.retry_limit - retry_count - 1}")
                    
                    # 计算剩余未成交数量
                    volume_left = volume_original - volume_traded
                    if volume_left > 0:
                        # 使用更激进的偏移量
                        retry_offset = ds.retry_offset_ticks
                        
                        # 判断买卖方向调用对应函数
                        if data.get('Direction') == '0': # 买
                            # 判断是买开还是买平
                            if offset_flag == '0': # 买开
                                # 记录新的重发订单，重试次数+1
                                # 注意：这里不能直接用buy返回的OrderSysID，因为是异步的
                                # 我们通过在ds中设置临时标记，让_on_order回调知道这个新订单是重发的
                                ds.buy(volume=volume_left, reason=f"超时重发(#{retry_count+1})", offset_ticks=retry_offset)
                                
                                # 将重试次数传给下一个订单
                                # 由于此时不知道新订单号，我们只能等新订单生成时处理
                                # 这里简化处理：我们假设重发总能成功提交，实际逻辑可能更复杂
                            else: # 买平 (平空)
                                ds.buycover(volume=volume_left, reason=f"超时重发(#{retry_count+1})", offset_ticks=retry_offset)
                        else: # 卖
                            # 判断是卖开还是卖平
                            if offset_flag == '0': # 卖开 (做空)
                                ds.sellshort(volume=volume_left, reason=f"超时重发(#{retry_count+1})", offset_ticks=retry_offset)
                            else: # 卖平 (平多)
                                ds.sell(volume=volume_left, reason=f"超时重发(#{retry_count+1})", offset_ticks=retry_offset)
                        
                        # 【关键】设置一个临时属性，告诉_on_order下一个生成的订单需要继承重试次数
                        ds._next_order_retry_count = retry_count + 1
                else:
                    print(f"[智能追单] 达到最大重试次数 ({ds.retry_limit})，停止追单")
                break

        # 调用用户自定义的撤单回调
        if self.on_cancel_callback:
            try:
                self.on_cancel_callback(data)
            except Exception as e:
                print(f"[用户撤单回调错误] {e}")
    
    def _on_position(self, data: Dict):
        """持仓回调 - 处理CTP返回的持仓数据（累加模式）
        
        注意：CTP 返回的是持仓明细，同一合约可能有多条记录（不同开仓日期）
        需要累加所有 Position > 0 的记录，忽略 Position = 0 的记录
        """
        symbol = data['InstrumentID']
        posi_direction = data['PosiDirection']
        position = data.get('Position', 0)
        today_pos = data.get('TodayPosition', 0)
        # 【关键修复】上海期货交易所(SHFE)和能源交易中心(INE)的YdPosition字段不可靠
        # 正确的昨仓计算方式：昨仓 = 总持仓 - 今仓
        # 这样无论哪个交易所都能正确计算昨仓
        yd_pos = position - today_pos  # 不再使用 data.get('YdPosition', 0)
        
        # 更新持仓到适配器级别的字典（按symbol+direction作为键）
        if not hasattr(self, '_position_cache'):
            self._position_cache = {}  # {(symbol, direction): {position, today, yd}}
        
        cache_key = (symbol, posi_direction)
        
        # 使用累加模式：CTP 返回的是持仓明细，同一合约可能有多条记录
        # Position > 0 的记录需要累加，Position = 0 的记录忽略（不删除已有数据）
        if position > 0:
            if cache_key in self._position_cache:
                # 累加到已有数据
                self._position_cache[cache_key]['position'] += position
                self._position_cache[cache_key]['today'] += today_pos
                self._position_cache[cache_key]['yd'] += yd_pos
            else:
                # 新建记录
                self._position_cache[cache_key] = {
                    'position': position,
                    'today': today_pos,
                    'yd': yd_pos
                }
        # Position=0 的记录直接忽略，不删除已有数据
        
        # 调用用户自定义的持仓回调
        if self.on_position_callback:
            try:
                self.on_position_callback(data)
            except Exception as e:
                print(f"[用户持仓回调错误] {e}")
    
    def _on_position_complete(self):
        """
        持仓查询完成回调 - 合并多空持仓
        
        注意：CTP会在每个品种查询完成时调用此方法
        我们使用计数器来判断是否所有品种都查询完成
        """
        # 初始化完成计数器（如果不存在）
        if not hasattr(self, '_position_query_complete_count'):
            self._position_query_complete_count = 0
        
        self._position_query_complete_count += 1
        
        # 获取需要查询的品种数量
        if hasattr(self, '_pending_position_queries'):
            expected_count = len(self._pending_position_queries)
        else:
            expected_count = 1  # 单品种模式
        
        # 只有当所有品种都查询完成后才合并持仓
        if self._position_query_complete_count < expected_count:
            return
        
        # 重置计数器
        self._position_query_complete_count = 0
        
        # 从适配器级别的缓存中提取持仓数据
        # _position_cache: {(symbol, direction): {position, today, yd}}
        position_cache = getattr(self, '_position_cache', {})
        
        # 按品种汇总多空持仓（使用大写键统一存储，解决大小写不敏感匹配）
        symbol_positions = {}  # {symbol_upper: {long, short, long_today, ...}}
        symbol_original = {}   # {symbol_upper: original_symbol} 保存原始大小写
        
        for (symbol, direction), pos_data in position_cache.items():
            symbol_upper = symbol.upper()
            if symbol_upper not in symbol_positions:
                symbol_positions[symbol_upper] = {
                    'long': 0, 'short': 0,
                    'long_today': 0, 'short_today': 0,
                    'long_yd': 0, 'short_yd': 0
                }
                symbol_original[symbol_upper] = symbol
            
            if direction == '2':  # 多头
                symbol_positions[symbol_upper]['long'] = pos_data['position']
                symbol_positions[symbol_upper]['long_today'] = pos_data['today']
                symbol_positions[symbol_upper]['long_yd'] = pos_data['yd']
            elif direction == '3':  # 空头
                symbol_positions[symbol_upper]['short'] = pos_data['position']
                symbol_positions[symbol_upper]['short_today'] = pos_data['today']
                symbol_positions[symbol_upper]['short_yd'] = pos_data['yd']
        
        # 【调试】打印查询到的持仓数据
        if symbol_positions:
            print(f"[持仓查询] CTP返回的持仓数据:")
            for sym_upper, pos_data in symbol_positions.items():
                orig_sym = symbol_original.get(sym_upper, sym_upper)
                long_pos = pos_data.get('long', 0)
                short_pos = pos_data.get('short', 0)
                if long_pos > 0 or short_pos > 0:
                    print(f"  - {orig_sym}: 多头={long_pos}手, 空头={short_pos}手")
        
        # 【辅助函数】提取品种代码（去除数字后缀）
        def extract_variety_code(symbol: str) -> str:
            """从合约代码提取品种代码，如 SC2603 -> SC"""
            import re
            match = re.match(r'^([a-zA-Z]+)', symbol)
            return match.group(1).upper() if match else symbol.upper()
        
        # 构建品种代码到持仓数据的映射（用于模糊匹配旧合约）
        variety_positions = {}  # {variety_upper: {symbol_upper: pos_data}}
        for sym_upper, pos_data in symbol_positions.items():
            variety = extract_variety_code(sym_upper)
            if variety not in variety_positions:
                variety_positions[variety] = {}
            variety_positions[variety][sym_upper] = pos_data
        
        # 将持仓数据同步到所有数据源
        # 优先精确匹配，如果没匹配到则按品种代码模糊匹配（支持旧合约换月）
        for ds in self.multi_data_source.data_sources:
            symbol_upper = ds.symbol.upper()
            pos_data = symbol_positions.get(symbol_upper, {})
            
            # 【关键修复】如果精确匹配没有持仓，尝试按品种代码模糊匹配
            # 这样旧合约（如SC2603）的持仓可以同步到新合约（如SC2604）的数据源
            if not pos_data or (pos_data.get('long', 0) == 0 and pos_data.get('short', 0) == 0):
                ds_variety = extract_variety_code(symbol_upper)
                if ds_variety in variety_positions:
                    # 找到该品种的所有持仓合约
                    variety_contracts = variety_positions[ds_variety]
                    for contract_upper, contract_pos in variety_contracts.items():
                        # 只同步有持仓的合约（避免覆盖已有持仓）
                        if contract_pos.get('long', 0) > 0 or contract_pos.get('short', 0) > 0:
                            if contract_upper != symbol_upper:
                                # 找到旧合约持仓，同步到当前数据源
                                pos_data = contract_pos
                                orig_sym = symbol_original.get(contract_upper, contract_upper)
                                print(f"[持仓同步] 旧合约 {orig_sym} 的持仓已同步到数据源 {ds.symbol}")
                                # 【重要】保存旧合约代码，平仓时需要使用
                                ds._old_contract = orig_sym
                            break
            
            long_pos = pos_data.get('long', 0)
            short_pos = pos_data.get('short', 0)
            long_today = pos_data.get('long_today', 0)
            short_today = pos_data.get('short_today', 0)
            long_yd = pos_data.get('long_yd', 0)
            short_yd = pos_data.get('short_yd', 0)
            
            # 计算净持仓
            net_pos = long_pos - short_pos
            net_today = long_today - short_today
            net_yd = long_yd - short_yd
            
            # 更新到数据源
            ds.current_pos = net_pos
            ds.today_pos = net_today
            ds.yd_pos = net_yd
            ds.long_pos = long_pos
            ds.short_pos = short_pos
            ds.long_today = long_today
            ds.short_today = short_today
            ds.long_yd = long_yd
            ds.short_yd = short_yd
        
        # 调用用户自定义的持仓查询完成回调
        if self.on_position_complete_callback:
            try:
                self.on_position_complete_callback()
            except Exception as e:
                print(f"[用户持仓查询完成回调错误] {e}")
        
        # 设置持仓查询完成事件
        self._position_query_done.set()
    
    def _on_order_error(self, error_id: int, error_msg: str, instrument_id: str = ""):
        """订单错误回调"""
        # 添加常见错误码说明（简洁版，只用中文描述）
        error_descriptions = {
            22: "合约不存在或未订阅",
            23: "报单价格不合法",
            30: "平仓数量超出持仓数量",
            31: "报单超过最大下单量",
            36: "资金不足",
            42: "成交价格不合法",
            44: "价格超出涨跌停板限制",
            50: "平今仓位不足，请改用平昨仓",
            51: "持仓不足或持仓方向错误",
            58: "报单已撤销",
            63: "重复报单",
            68: "每秒报单数超过限制",
            76: "撤单已提交到交易所，请稍后",
            81: "风控原因拒绝报单",
            85: "非法报单，CTP拒绝",
            90: "休眠时间不允许报单",
            91: "错误的开仓标志",
            95: "CTP不支持的价格类型（限价单/市价单）",
        }
        
        # 优先使用简洁的中文描述
        desc = error_descriptions.get(error_id, error_msg or "未知错误")
        symbol_str = f" {instrument_id}" if instrument_id else ""
        print(f"❌ [订单错误]{symbol_str} 错误码={error_id} - {desc}")
        
        # 调用用户自定义的报单错误回调
        if self.on_order_error_callback:
            try:
                self.on_order_error_callback({
                    'ErrorID': error_id,
                    'ErrorMsg': desc,
                    'InstrumentID': instrument_id
                })
            except Exception as e:
                print(f"[用户报单错误回调错误] {e}")
    
    def _on_cancel_error(self, error_id: int, error_msg: str):
        """撤单错误回调"""
        # 常见撤单错误码
        error_descriptions = {
            25: "撤单报单已全成交",
            26: "撤单被拒绝：订单已成交",
            76: "撤单已提交到交易所，请稍后",
            77: "撤单报单被拒绝：没有可撤的单",
        }
        
        desc = error_descriptions.get(error_id, "")
        if desc:
            print(f"❌ [撤单错误] 错误码={error_id} - {desc}")
        else:
            print(f"❌ [撤单错误] 错误码={error_id} - {error_msg}")
        
        # 调用用户自定义的撤单错误回调
        if self.on_cancel_error_callback:
            try:
                self.on_cancel_error_callback({
                    'ErrorID': error_id,
                    'ErrorMsg': desc or str(error_msg)
                })
            except Exception as e:
                print(f"[用户撤单错误回调错误] {e}")
    
    def _on_disconnect(self, source: str, reason: int):
        """
        连接断开回调
        
        Args:
            source: 断开的连接类型，'md'=行情服务器, 'trader'=交易服务器
            reason: 断开原因代码（CTP定义的错误码）
        """
        source_name = '行情服务器' if source == 'md' else '交易服务器'
        
        # 断开原因说明
        reason_map = {
            0x1001: '网络读取失败',
            0x1002: '网络写入失败', 
            0x2001: '接收心跳超时',
            0x2002: '发送心跳超时',
            0x2003: '收到错误报文',
        }
        reason_desc = reason_map.get(reason, '未知原因')
        
        print(f"\n{'!' * 60}")
        print(f"[CTP断开] {source_name} 连接断开!")
        print(f"[CTP断开] 原因码: {reason:#x} ({reason}) - {reason_desc}")
        print(f"{'!' * 60}\n")
        
        # 调用用户自定义的断开连接回调
        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback(source, reason)
            except Exception as e:
                print(f"[用户断开回调错误] {e}")
    
    def _on_account(self, data: Dict):
        """账户资金回调"""
        # 更新内部账户信息
        self.account_info = {
            'balance': data.get('Balance', 0),
            'available': data.get('Available', 0),
            'position_profit': data.get('PositionProfit', 0),
            'close_profit': data.get('CloseProfit', 0),
            'commission': data.get('Commission', 0),
            'frozen_margin': data.get('FrozenMargin', 0),
            'curr_margin': data.get('CurrMargin', 0),
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        # 调用用户自定义的账户回调
        if self.on_account_callback:
            try:
                self.on_account_callback(data)
            except Exception as e:
                print(f"[用户账户回调错误] {e}")
    
    def _log(self, message: str):
        """日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def stop(self):
        """停止运行"""
        print("\n[实盘适配器] 停止运行...")
        self.running = False
        
        # 保存所有数据源的当前未完成K线
        if self.multi_data_source:
            for ds in self.multi_data_source.data_sources:
                recorder_key = f"{ds.symbol}_{ds.kline_period}"
                if ds.current_kline is not None and recorder_key in self.data_recorders:
                    print(f"[数据记录器] 保存 {recorder_key} 当前未完成的K线")
                    self.data_recorders[recorder_key].record_kline(ds.current_kline)
        
        # 等待所有数据写入完成
        for symbol, recorder in self.data_recorders.items():
            recorder.flush_all()
        
        # 停止后台写入线程
        DataRecorder.stop_write_thread()
        
        # 释放CTP资源
        if self.ctp_client:
            self.ctp_client.release()
        
        print("[实盘适配器] 已停止")
