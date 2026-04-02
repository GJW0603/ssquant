#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交易配置文件

支持自动获取合约参数（合约乘数、最小跳动、保证金率、手续费率）
"""

from ..backtest.unified_runner import RunMode

# 延迟导入合约信息服务（避免循环导入）
_contract_service = None

def _get_contract_params(symbol: str) -> dict:
    """获取合约交易参数"""
    global _contract_service
    if _contract_service is None:
        try:
            from ..data.contract_info import get_trading_params
            _contract_service = get_trading_params
        except ImportError:
            print("[配置] 警告：合约信息服务不可用，使用默认参数")
            return {}
    return _contract_service(symbol)


def _resolve_continuous_symbol_for_live(symbol: str) -> str:
    """
    SIMNOW/实盘：将 rb888、rb777 等连续合约代码解析为交易所当前实际合约（用于 CTP 订阅与下单）。
    解析失败或网络不可用时保留原代码并打印警告。
    """
    if not symbol or not isinstance(symbol, str):
        return symbol
    try:
        from ..data.contract_mapper import ContractMapper
        if not ContractMapper.is_continuous(symbol):
            return symbol
        params = _get_contract_params(symbol)
        if not params:
            return symbol
        actual = params.get('actual_symbol') or symbol
        if actual and actual.strip() and actual.lower() != symbol.lower():
            print(f"[实盘配置] 连续合约 {symbol} -> {actual}（CTP 订阅/下单使用实际合约）")
            return actual.strip()
    except Exception as e:
        print(f"[实盘配置] 连续合约解析失败，保留 {symbol}: {e}")
    return symbol


def _apply_live_continuous_symbol_resolution(mode: RunMode, config: dict) -> None:
    """原地修改 config：仅 SIMNOW/实盘 将 symbol / data_sources[].symbol 中的主连转为实际合约。"""
    if mode not in (RunMode.SIMNOW, RunMode.REAL_TRADING):
        return
    if config.get('resolve_continuous_live') is False:
        return
    sym = config.get('symbol')
    if sym:
        config['symbol'] = _resolve_continuous_symbol_for_live(sym)
    sources = config.get('data_sources')
    if isinstance(sources, list):
        for ds in sources:
            if isinstance(ds, dict) and ds.get('symbol'):
                old = ds['symbol']
                ds['symbol'] = _resolve_continuous_symbol_for_live(old)


# ========== 远程数据API认证 quant789.com(松鼠俱乐部会员) ========== 小松鼠VX：viquant01
API_USERNAME = ""              # 鉴权账号 (您的俱乐部手机号或邮箱)
API_PASSWORD = ""            # 鉴权密码 

# ========== 复权设置 ==========
# 复权数据处理策略:
#   - data_server（远程服务器）只存储不复权(raw)数据
#   - 从 data_server 获取数据后，由框架本地进行复权计算
#   - 本地复权算法位于: ssquant/data/local_adjust.py
#   - adjust_type: '0'=不复权, '1'=后复权, '2'=前复权
ENABLE_REMOTE_ADJUST = True


# ========== 回测默认配置 ==========
BACKTEST_DEFAULTS = {
    # -------- 资金配置 --------
    'initial_capital': 20000,       # 初始资金 (元)
    'commission': 0.0001,           # 手续费率 (万分之一)
    'margin_rate': 0.1,             # 保证金率 (10%)
    
    # -------- 合约参数 --------
    'contract_multiplier': 10,      # 合约乘数 (吨/手)
    'price_tick': 1.0,              # 最小变动价位 (元)
    'slippage_ticks': 1,            # 滑点跳数
    'adjust_type': '1',             # 复权类型: '0'不复权, '1'后复权, '2'前复权
    
    # -------- 数据对齐配置 (多数据源时使用) --------
    'align_data': False,            # 默认不开启，是否对齐多数据源的时间索引 (跨周期过滤策略需开启)
    'fill_method': 'ffill',         # 缺失值填充方法: 'ffill'向前填充, 'bfill'向后填充
    
    # -------- 数据窗口配置 --------
    'lookback_bars': 0,           # K线回溯窗口大小，0表示不限制（返回全部历史数据），建议设置500-2000
    
    # -------- 缓存与调试 --------
    'use_cache': True,              # 是否使用本地缓存数据
    'save_data': True,              # 是否保存数据到本地缓存
    'debug': False,                 # 是否开启调试模式
    # -------- 实盘 Tick 队列配置（回测中无影响，保留统一入口） --------
    'tick_queue_maxsize': 20000,    # Tick处理队列最大长度。高频多品种建议 10000-50000
}


# ========== 账户配置 ==========
# 在此定义所有账户，策略中通过 account='账户名' 使用
ACCOUNTS = {
    
    # -------------------- SIMNOW 模拟账户 --------------------
    'simnow_default': {
        # 账户认证 (必填)
        'investor_id': '',                # SIMNOW账号 (在 simnow.com.cn 注册)
        'password': '',                   # SIMNOW密码
        'server_name': '电信1',            # 服务器: '电信1', '电信2', '移动', 'TEST', '24hour'
        
        # 交易参数
        'kline_period': '1m',             # K线周期: '1m', '5m', '15m', '30m', '1h', '1d'
        'price_tick': 1.0,                # 最小变动价位 (螺纹钢=1, 黄金=0.02)
        'order_offset_ticks': 5,          # 委托价格偏移跳数 (超价下单，确保成交)
        
        # 智能算法交易配置
        'algo_trading': False,             # 是否启用算法交易
        'order_timeout': 10,              # 订单超时时间(秒)，0表示不启用
        'retry_limit': 3,                 # 最大重试次数
        'retry_offset_ticks': 5,          # 重试时的超价跳数 (相对于对手价)
        
        # 数据配置
        'preload_history': True,          # 是否预加载历史K线
        'history_lookback_bars': 100,     # 预加载K线数量
        'lookback_bars': 0,               # K线/TICK缓存窗口大小，0表示使用默认值(1000条)，建议设置500-2000
        'adjust_type': '1',               # 复权类型: '0'不复权, '1'后复权, '2'前复权
        # 'history_symbol': 'rb888',      # 自定义历史数据源 (默认自动推导为主力XXX888)
                                         # 跨期套利时可指定: 主力用'rb888', 次主力用'rb777'
        
        # K线数据源配置
        # 'kline_source': 'local',        # K线数据源: 'local'(默认,CTP本地聚合) 或 'data_server'(远程推送)
        
        # 回调配置
        'enable_tick_callback': False,     # 是否启用TICK回调 (实时行情推送)
        # data_server + tick回调 节流间隔（秒）
        # 仅 kline_source='data_server' 且 enable_tick_callback=True 时生效
        # 作用：避免开盘tick洪峰导致队列积压/假死（多品种场景尤其明显）
        # 设为 0 可关闭节流（每个tick都触发策略，适合需要逐tick止盈止损的策略）
        'tick_callback_interval': 0.5,
        # Tick队列容量（实盘高频保护）
        # 建议:
        #   - 低频/少品种: 5000-10000
        #   - 中频/10~20品种: 15000-30000
        #   - 高频/30+品种或夜盘活跃时段: 30000-50000
        # 调大后更能抗瞬时洪峰，但会占用更多内存；如果日志中频繁出现
        # “Tick队列已满/积压压缩”，优先从 20000 提升到 30000 或 50000。
        'tick_queue_maxsize': 20000,
        
        # -------- 自动换月（仅 SIMNOW/实盘；回测不支持，勿在 RunMode.BACKTEST 里依赖）--------
        # auto_roll_mode：发单节奏（与 reopen 不冲突）。'simultaneous'=同一次策略回调里连发委托、不等上一笔成交；
        #   reopen=True 时先发平旧再发开新（两笔）；reopen=False 时只发平旧（一笔）。
        # 'sequential'=先只发平旧，旧腿平仓闭环后再发开新（reopen=False 时仅平旧）；适合希望开新晚于平旧成交的场景。
        # 用法：get_config(..., auto_roll_enabled=True, auto_roll_mode='simultaneous' 或 'sequential')；
        #       多品种可在 data_sources[] 里对某一品种单独写 auto_roll_*。
        'auto_roll_enabled': False,       # True=框架在策略前自动移仓；False=不启用
        'auto_roll_mode': 'simultaneous', # 见上，一般保持 'simultaneous'
        'auto_roll_reopen': True,         # 是否在新主力补回仓位；与 mode 分工不同，见上段
        'auto_roll_order_type': 'next_bar_open',  # 移仓下单方式，与策略里 order_type 含义一致
        'auto_roll_close_offset_ticks': None,     # 平旧限价跳数；None=用上面 order_offset_ticks
        'auto_roll_open_offset_ticks': None,      # 开新限价跳数；None=用上面 order_offset_ticks
        'auto_roll_verify_timeout_bars': 500,     # 移仓后闭环超时（策略调用次数上限，超时重置防死循环）
        'auto_roll_log_enabled': True,    # True=写移仓专用本地日志（复盘）；False=不写
        'auto_roll_log_dir': None,         # 日志目录；None=默认 ./live_data/rollover_logs（可写绝对路径）
        'auto_roll_log_jsonl': False,      # True=同时写 jsonl 便于程序解析
        
        # 数据保存配置 (默认全部关闭)
        'save_kline_csv': False,           # 是否保存K线到CSV文件
        'save_kline_db': True,            # 是否保存K线到数据库
        'save_tick_csv': False,            # 是否保存TICK到CSV文件
        'save_tick_db': False,            # 是否保存TICK到数据库
        'data_save_path': './live_data',  # CSV文件保存路径
        'db_path': 'data_cache/backtest_data.db',  # 数据库路径
    },
    
    # -------------------- 实盘账户 --------------------
    'real_default': {
        # 账户认证 (必填，向期货公司获取)
        'broker_id': '',                  # 期货公司代码 (如: '9999')
        'investor_id': '',                # 资金账号
        'password': '',                   # 交易密码
        'md_server': '',                  # 行情服务器地址 (如: 'tcp://180.168.146.187:10211')
        'td_server': '',                  # 交易服务器地址 (如: 'tcp://180.168.146.187:10201')
        'app_id': '',                     # 应用ID (向期货公司申请)
        'auth_code': '',                  # 授权码 (向期货公司申请)
        
        # 交易参数
        'kline_period': '1d',             # K线周期: '1m', '5m', '15m', '30m', '1h', '1d'
        'price_tick': 1.0,                # 最小变动价位 (螺纹钢=1, 黄金=0.02)
        'order_offset_ticks': 5,          # 委托价格偏移跳数 (超价下单，确保成交)
        
        # 智能算法交易配置
        'algo_trading': False,             # 是否启用算法交易
        'order_timeout': 10,              # 订单超时时间(秒)，0表示不启用
        'retry_limit': 3,                 # 最大重试次数
        'retry_offset_ticks': 5,          # 重试时的超价跳数 (相对于对手价)
        
        # 数据配置
        'preload_history': True,          # 是否预加载历史K线
        'history_lookback_bars': 100,     # 预加载K线数量
        'lookback_bars': 0,               # K线/TICK缓存窗口大小，0表示使用默认值(1000条)，建议设置500-2000
        'adjust_type': '1',               # 复权类型: '0'不复权, '1'后复权, '2'前复权
        # 'history_symbol': 'rb888',      # 自定义历史数据源 (默认自动推导为主力XXX888)
                                         # 跨期套利时可指定: 主力用'rb888', 次主力用'rb777'
        
        # K线数据源配置
        # 'kline_source': 'local',        # K线数据源: 'local'(默认,CTP本地聚合) 或 'data_server'(远程推送)
        
        # 回调配置
        'enable_tick_callback': False,     # 是否启用TICK回调 (实时行情推送)
        # data_server + tick回调 节流间隔（秒）
        # 仅 kline_source='data_server' 且 enable_tick_callback=True 时生效
        # 作用：避免开盘tick洪峰导致队列积压/假死（多品种场景尤其明显）
        # 设为 0 可关闭节流（每个tick都触发策略，适合需要逐tick止盈止损的策略）
        'tick_callback_interval': 0.5,
        # Tick队列容量（实盘高频保护）
        # 推荐先用 20000；若云服务器 CPU 足够、品种较多、夜盘高频活跃，
        # 可上调到 30000-50000。若内存紧张或品种少，可降到 10000。
        'tick_queue_maxsize': 20000,
        
        # -------- 自动换月（仅实盘；回测不支持）--------
        # auto_roll_mode / auto_roll_reopen：与 simnow 段说明相同（发单节奏 vs 是否补开新仓）。
        'auto_roll_enabled': False,       # True=框架策略前自动移仓；False=不启用
        'auto_roll_mode': 'simultaneous', # 见 simnow 段
        'auto_roll_reopen': True,         # 见 simnow 段
        'auto_roll_order_type': 'next_bar_open',  # 移仓委托类型
        'auto_roll_close_offset_ticks': None,     # 平旧跳数；None=用 order_offset_ticks
        'auto_roll_open_offset_ticks': None,      # 开新跳数；None=用 order_offset_ticks
        'auto_roll_verify_timeout_bars': 500,     # 闭环等待上限（策略调用次数）
        'auto_roll_log_enabled': True,    # True=写移仓本地日志便于审计复盘
        'auto_roll_log_dir': None,         # 日志目录；None=默认 live_data/rollover_logs
        'auto_roll_log_jsonl': False,      # True=额外 jsonl 行格式
        
        # 数据保存配置 (默认全部关闭)
        'save_kline_csv': False,          # 是否保存K线到CSV文件
        'save_kline_db': True,           # 是否保存K线到数据库
        'save_tick_csv': False,           # 是否保存TICK到CSV文件
        'save_tick_db': False,            # 是否保存TICK到数据库
        'data_save_path': './live_data',  # CSV文件保存路径
        'db_path': 'data_cache/backtest_data.db',  # 数据库路径
    },
}




def get_config(mode: RunMode, account: str = None, auto_params: bool = True, **overrides):
    """
    获取配置（支持自动获取合约参数）
    
    Args:
        mode: 运行模式
        account: 账户名 (SIMNOW/实盘必填，从 ACCOUNTS 中选择)
        auto_params: 是否自动获取合约参数（默认 True）
                    自动获取: contract_multiplier, price_tick, margin_rate, commission
        **overrides: 覆盖参数 (如 symbol='rb2601')
    
    常用覆盖参数:
        symbol: 合约代码（支持 au2602, au888, au 等格式）
        kline_period: K线周期
        preload_history: 是否预加载历史数据
        history_lookback_bars: 预加载K线数量
        history_symbol: 自定义历史数据源 (跨期套利用)
                       - 不指定: 自动推导为主力连续(XXX888)
                       - 'rb888': 主力连续
                       - 'rb777': 次主力连续
        
        SIMNOW/实盘 专用:
        resolve_continuous_live: 默认 True。为 True 时，symbol / data_sources[].symbol 中的
            XXX888、XXX777 会先解析为 contract_info 中的当前实际合约再用于 CTP（订阅/下单）。
            设为 False 可关闭替换（一般无需关闭）。
        
        数据请求参数（回测模式，三选一可组合）:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
        start_time: 精确开始时间 'YYYY-MM-DD HH:MM:SS'
        end_time: 精确结束时间 'YYYY-MM-DD HH:MM:SS'
        limit: BAR线数量，获取最近N根K线
    
    示例:
        # 回测 - 日期范围
        config = get_config(RunMode.BACKTEST, symbol='au888', 
                           start_date='2025-01-01', end_date='2025-12-31')
        
        # 回测 - 精确时间范围
        config = get_config(RunMode.BACKTEST, symbol='au888', kline_period='1m',
                           start_time='2026-02-10 09:00:00', end_time='2026-02-14 15:00:00')
        
        # 回测 - 最近N根K线
        config = get_config(RunMode.BACKTEST, symbol='au888', kline_period='1m',
                           limit=1000)
        
        # 回测 - 从某日开始取N根
        config = get_config(RunMode.BACKTEST, symbol='au888', kline_period='5m',
                           start_date='2026-01-01', limit=500)
        
        # SIMNOW - 自动获取参数
        config = get_config(RunMode.SIMNOW, account='simnow_default', symbol='au2602')
        
        # 禁用自动参数
        config = get_config(RunMode.BACKTEST, auto_params=False, symbol='au888', ...)
    """
    if mode == RunMode.BACKTEST:
        config = BACKTEST_DEFAULTS.copy()
    elif mode in (RunMode.SIMNOW, RunMode.REAL_TRADING):
        if not account:
            raise ValueError(f"运行模式 {mode.value} 必须指定 account 参数")
        if account not in ACCOUNTS:
            available = ', '.join(ACCOUNTS.keys())
            raise ValueError(f"账户 '{account}' 不存在，可用: {available}")
        config = ACCOUNTS[account].copy()
    else:
        raise ValueError(f"不支持的运行模式: {mode}")
    
    # 应用用户覆盖参数
    config.update(overrides)
    
    # SIMNOW/实盘：配置中写 rb888、rb777 时替换为当前主力/次主力实际合约（CTP 需真实 InstrumentID）
    _apply_live_continuous_symbol_resolution(mode, config)
    
    # 如果启用了 data_server K线模式，自动填充连接配置
    # 默认包含 _server_config.DATA_SERVER（含 ws_url/api_url/fallback_servers 主备轮询）
    # 账户里可只覆盖部分键；若需自定义备选，在 data_server 中提供 fallback_servers 列表
    if config.get('kline_source') == 'data_server':
        from ._server_config import DATA_SERVER as _DS
        if 'data_server' not in config:
            config['data_server'] = _DS.copy()
        else:
            merged_ds = _DS.copy()
            merged_ds.update(config['data_server'])
            config['data_server'] = merged_ds
    
    # 自动获取合约参数
    if auto_params:
        symbol = config.get('symbol', '')
        if symbol:
            contract_params = _get_contract_params(symbol)
            if contract_params:
                # 需要自动填充的参数列表（包括固定金额手续费）
                auto_keys = [
                    'contract_multiplier', 'price_tick', 'margin_rate', 'commission',
                    'commission_per_lot', 'commission_close_per_lot', 'commission_close_today_per_lot'
                ]
                
                # 只填充用户未手动指定的参数
                auto_filled = []
                for key in auto_keys:
                    if key not in overrides:  # 用户未手动指定
                        if key in contract_params:
                            config[key] = contract_params[key]
                            # 只显示主要参数，不显示手续费细节
                            if key in ['contract_multiplier', 'price_tick', 'margin_rate']:
                                auto_filled.append(f"{key}={contract_params[key]}")
                
                # 显示手续费类型
                comm_per_lot = contract_params.get('commission_per_lot', 0)
                if comm_per_lot > 0:
                    auto_filled.append(f"手续费={comm_per_lot}元/手")
                elif contract_params.get('commission', 0) > 0:
                    auto_filled.append(f"手续费率={contract_params.get('commission', 0)}")
                
                if auto_filled:
                    variety_name = contract_params.get('variety_name', '')
                    actual_symbol = contract_params.get('actual_symbol', symbol)
                    name_info = f"({variety_name})" if variety_name else ""
                    print(f"[自动参数] {symbol}{name_info} -> {', '.join(auto_filled)}")
                    
                    # 如果是主力连续，提示实际合约
                    if '888' in symbol or '777' in symbol:
                        print(f"[自动参数] {symbol} 当前主力合约: {actual_symbol}")
    
    return config


def get_api_auth():
    """获取数据API认证"""
    return API_USERNAME, API_PASSWORD


def set_api_auth(username: str, password: str):
    """设置数据API认证"""
    global API_USERNAME, API_PASSWORD
    API_USERNAME = username
    API_PASSWORD = password


def add_account(name: str, **config):
    """添加账户"""
    ACCOUNTS[name] = config


def list_accounts():
    """列出所有账户"""
    return list(ACCOUNTS.keys())
