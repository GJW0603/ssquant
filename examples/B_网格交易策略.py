"""
网格交易策略 - 统一运行版本

支持三种运行模式:
1. 历史数据回测
2. SIMNOW模拟交易  
3. 实盘CTP交易

策略逻辑:
1. 设定价格区间和网格数量
2. 价格每下跌一格，买入1手
3. 价格每上涨一格，卖出1手
4. 实现低买高卖的网格交易

适用场景:
- 震荡行情效果好
- 单边行情需要止损保护

合约代码 symbol 怎么填：
  回测：品种+888 = 主力连续合约，用于拉取连续K线（如 au888、rb888）
  SIMNOW / 实盘（自动主力映射）：
    au888  → 自动映射为当前主力月份（如 au888→au2508），用于CTP订阅和下单
    au777  → 自动映射为次主力月份
    au2508 → 指定月份，直接使用，不做映射

自动移仓（仅 SIMNOW/实盘）：持仓过主力换月时，开启 auto_roll_enabled=True 即可自动平旧开新
合约参数（乘数、最小变动价、手续费等）自动获取，无需手动填写
复权 adjust_type：'0'=不复权  '1'=后复权  '2'=前复权
K线来源 kline_source（仅 SIMNOW/实盘）：'local'=本地CTP Tick合成（默认）  'data_server'=远程推送
账户配置：在 trading_config.py 的 ACCOUNTS 中填写CTP账号信息
"""

from ssquant.api.strategy_api import StrategyAPI
from ssquant.backtest.unified_runner import UnifiedStrategyRunner, RunMode
from ssquant.config.trading_config import get_config


# ========== 全局状态变量 ==========
g_grid_initialized = False      # 网格是否已初始化
g_base_price = 0                # 基准价格（网格中心）
g_grid_spacing = 0              # 网格间距
g_last_level = 0                # 上一次价格所在的网格层级


def initialize(api: StrategyAPI):
    """策略初始化函数"""
    global g_grid_initialized, g_base_price, g_grid_spacing, g_last_level
    
    api.log("=" * 60)
    api.log("网格交易策略初始化")
    api.log("=" * 60)
    
    # 获取策略参数
    grid_spacing = api.get_param('grid_spacing', 20.0)  # 网格间距
    max_pos = api.get_param('max_pos', 5)               # 最大持仓
    
    api.log(f"参数设置:")
    api.log(f"  网格间距: {grid_spacing} 元")
    api.log(f"  最大持仓: {max_pos} 手")
    api.log(f"  策略逻辑: 价格每下跌一格买入1手，每上涨一格卖出1手")
    api.log("=" * 60)
    
    # 重置状态
    g_grid_initialized = False
    g_base_price = 0
    g_grid_spacing = 0
    g_last_level = 0


def grid_strategy(api: StrategyAPI):
    """
    网格交易策略
    
    策略逻辑:
    1. 以首次价格为基准，计算当前价格所在的网格层级
    2. 层级 = (当前价格 - 基准价格) / 网格间距
    3. 层级下降（价格下跌）→ 买入
    4. 层级上升（价格上涨）→ 卖出
    
    示例（间距20元）:
    - 基准价3400，当前3400 → 层级0
    - 价格跌到3380 → 层级-1 → 买入1手
    - 价格跌到3360 → 层级-2 → 买入1手（共2手）
    - 价格涨到3380 → 层级-1 → 卖出1手（共1手）
    - 价格涨到3400 → 层级0 → 卖出1手（共0手）
    """
    global g_grid_initialized, g_base_price, g_grid_spacing, g_last_level
    
    # 获取当前价格（兼容回测和实盘）
    close = api.get_close()
    if close is None or len(close) == 0:
        return
    current_price = close.iloc[-1]  # 最新收盘价
    
    if current_price is None or current_price <= 0:
        return
    
    # 获取策略参数
    grid_spacing = api.get_param('grid_spacing', 20.0)
    max_pos = api.get_param('max_pos', 5)
    
    # 初始化
    if not g_grid_initialized:
        g_base_price = current_price
        g_grid_spacing = grid_spacing
        g_last_level = 0
        g_grid_initialized = True
        
        api.log(f"\n[网格初始化] 基准价格: {g_base_price:.2f}")
        api.log(f"  网格间距: {grid_spacing:.2f}")
        api.log(f"  最大持仓: {max_pos} 手")
        api.log(f"  当前层级: 0")
        return
    
    # 计算当前价格所在的网格层级
    # 层级 = floor((当前价格 - 基准价格) / 网格间距)
    current_level = int((current_price - g_base_price) / g_grid_spacing)
    
    # 获取当前持仓
    current_pos = api.get_pos()
    
    # 层级变化时交易
    if current_level != g_last_level:
        level_change = current_level - g_last_level
        
        if level_change < 0:
            # 层级下降（价格下跌）→ 买入
            # 每下降一个层级买入一手
            for _ in range(abs(level_change)):
                if current_pos < max_pos:
                    api.buy(volume=1, order_type='next_bar_open', 
                           reason=f'网格买入 层级{g_last_level}→{current_level}')
                    current_pos += 1
                    api.log(f"📉 [网格买入] 价格:{current_price:.2f} "
                           f"层级:{g_last_level}→{current_level} 持仓:{current_pos}")
                else:
                    api.log(f"⚠️ [买入受限] 已达最大持仓 {max_pos} 手")
                    break
        
        elif level_change > 0:
            # 层级上升（价格上涨）→ 卖出
            # 每上升一个层级卖出一手
            for _ in range(level_change):
                if current_pos > 0:
                    api.sell(volume=1, order_type='next_bar_open',
                            reason=f'网格卖出 层级{g_last_level}→{current_level}')
                    current_pos -= 1
                    api.log(f"📈 [网格卖出] 价格:{current_price:.2f} "
                           f"层级:{g_last_level}→{current_level} 持仓:{current_pos}")
                else:
                    # 没有多头持仓，可以做空（可选）
                    # api.sellshort(volume=1, order_type='next_bar_open')
                    break
        
        # 更新层级
        g_last_level = current_level


# =====================================================================
# 配置区
# =====================================================================

if __name__ == "__main__":
    
    # ========== 运行模式 ==========
    RUN_MODE = RunMode.SIMNOW  # 可选: BACKTEST, SIMNOW, REAL_TRADING
    
    # ========== 策略参数 ==========
    # 注意：grid_spacing 需要根据品种价格合理设置
    # 螺纹钢(3500元): 建议 20-50 元
    # 黄金(600元): 建议 2-5 元
    strategy_params = {
        'grid_spacing': 2,   # 网格间距（元）- 螺纹钢建议30元
        'max_pos': 5,           # 最大持仓（手）
    }
    
    # ========== 配置 ==========
    if RUN_MODE == RunMode.BACKTEST:
        # ==================== 回测配置 ====================
        config = get_config(RUN_MODE,
            # -------- 合约配置 --------
            symbol='rb888',                   # 品种+888 = 主力连续合约（回测时用于拉取连续K线）
            start_date='2025-12-01',          # 回测开始日期
            end_date='2026-01-31',            # 回测结束日期
            kline_period='1m',                # K线周期: 1m/5m/15m/30m/1h/1d
            adjust_type='1',                  # 复权: '0'不复权  '1'后复权  '2'前复权
            
            # -------- 合约参数（自动获取，无需手动填写）--------
            # price_tick=自动,                # 最小变动价位（自动从远程获取）
            # contract_multiplier=自动,       # 合约乘数（自动从远程获取）
            slippage_ticks=1,                 # 滑点跳数
            
            # -------- 资金配置 --------
            initial_capital=500000,           # 初始资金（网格策略需要更多资金）
            # commission=自动,                # 手续费率（自动从远程获取）
            # margin_rate=自动,               # 保证金率（自动从远程获取）
            
            # -------- 数据窗口配置 --------
            lookback_bars=500,                # K线回溯窗口 (0=不限制，策略get_klines返回的最大条数)
        )
    
    elif RUN_MODE == RunMode.SIMNOW:
        # ==================== SIMNOW模拟配置 ====================
        config = get_config(RUN_MODE,
            # -------- 账户配置 --------
            account='simnow_default',         # 账户名称（在trading_config.py的ACCOUNTS中定义）
            server_name='电信1',              # 服务器: 电信1/电信2/移动/TEST(盘后测试)
            
            # -------- K线数据来源 --------
            # 'local' = 本地CTP Tick合成K线（默认）  'data_server' = 远程推送（需配置账号密码）
            kline_source='data_server',
            
            # -------- 合约与周期 --------
            # 合约代码写法：
            #   rb888 → 主力合约（自动映射）  rb777 → 次主力  rb2508 → 指定月份
            symbol='rb888',
            kline_period='1m',                # K线周期
            
            # -------- 下单参数 --------
            # price_tick=自动,                # 最小变动价位（自动从远程获取）
            order_offset_ticks=5,             # 委托偏移跳数
            
            # -------- 智能算法交易配置 --------
            # 开启后，未成交的委托会自动撤单并以更优价格重新挂单
            algo_trading=False,               # 启用算法交易
            order_timeout=10,                 # 订单超时时间(秒)
            retry_limit=3,                    # 最大重试次数
            retry_offset_ticks=5,             # 重试时的超价跳数
            
            # -------- 自动移仓（主力合约换月）--------
            # 开启后，主力切换时自动平旧→开新，适合中长线策略
            auto_roll_enabled=False,           # 是否启用自动移仓
            auto_roll_reopen=True,             # 平旧仓后是否自动在新主力上补开仓位
            
            # -------- 历史数据配置 --------
            preload_history=True,             # 是否预加载历史K线
            history_lookback_bars=5000,         # 预加载K线数量
            adjust_type='1',                  # 复权: '0'不复权  '1'后复权  '2'前复权
            
            # -------- 数据窗口配置 --------
            lookback_bars=500,                # K线/TICK回溯窗口 (0=不限制，策略get_klines返回的最大条数)
            
            # -------- 回调模式配置 --------
            enable_tick_callback=False,       # TICK回调: True=每个TICK触发, False=每根K线触发
            
            # -------- 数据保存配置 --------
            save_kline_csv=False,             # 保存K线到CSV
            save_kline_db=False,              # 保存K线到数据库
            save_tick_csv=False,              # 保存TICK到CSV
            save_tick_db=False,               # 保存TICK到数据库
        )
    
    elif RUN_MODE == RunMode.REAL_TRADING:
        # ==================== 实盘配置 ====================
        config = get_config(RUN_MODE,
            # -------- 账户配置 --------
            account='real_default',           # 账户名称（在trading_config.py的ACCOUNTS中定义）
            # 实盘账户需要配置: broker_id, investor_id, password,
            #                  md_server, td_server, app_id, auth_code
            
            # -------- K线数据来源 --------
            # 'local' = 本地CTP Tick合成K线（默认）  'data_server' = 远程推送（需配置账号密码）
            # kline_source='data_server',
            
            # -------- 合约与周期 --------
            symbol='rb888',
            kline_period='1m',                # K线周期
            
            # -------- 下单参数 --------
            # price_tick=自动,                # 最小变动价位（自动从远程获取）
            order_offset_ticks=5,             # 委托偏移跳数
            
            # -------- 智能算法交易配置 --------
            # 开启后，未成交的委托会自动撤单并以更优价格重新挂单
            algo_trading=False,               # 启用算法交易
            order_timeout=10,                 # 订单超时时间(秒)
            retry_limit=3,                    # 最大重试次数
            retry_offset_ticks=5,             # 重试时的超价跳数
            
            # -------- 自动移仓（主力合约换月）--------
            # 开启后，主力切换时自动平旧→开新，适合中长线策略
            auto_roll_enabled=False,           # 是否启用自动移仓
            auto_roll_reopen=True,             # 平旧仓后是否自动在新主力上补开仓位
            
            # -------- 历史数据配置 --------
            preload_history=True,             # 是否预加载历史K线
            history_lookback_bars=50,         # 预加载K线数量
            adjust_type='1',                  # 复权: '0'不复权  '1'后复权  '2'前复权
            
            # -------- 数据窗口配置 --------
            lookback_bars=500,                # K线/TICK回溯窗口 (0=不限制，策略get_klines返回的最大条数)
            
            # -------- 回调模式配置 --------
            enable_tick_callback=False,       # TICK回调模式
            
            # -------- 数据保存配置 --------
            save_kline_csv=False,             # 保存K线到CSV
            save_kline_db=False,              # 保存K线到数据库
            save_tick_csv=False,              # 保存TICK到CSV
            save_tick_db=False,               # 保存TICK到数据库
        )
    
    # ========== 创建运行器并执行 ==========
    print("\n" + "=" * 60)
    print("网格交易策略 - 统一运行版本")
    print("=" * 60)
    print(f"运行模式: {RUN_MODE.value}")
    print(f"合约代码: {config['symbol']}")
    print(f"策略参数:")
    print(f"  网格间距: {strategy_params['grid_spacing']} 元")
    print(f"  最大持仓: {strategy_params['max_pos']} 手")
    print(f"  逻辑: 价格每下跌{strategy_params['grid_spacing']}元买1手，每上涨{strategy_params['grid_spacing']}元卖1手")
    print("=" * 60 + "\n")
    
    runner = UnifiedStrategyRunner(mode=RUN_MODE)
    runner.set_config(config)
    
    try:
        results = runner.run(
            strategy=grid_strategy,
            initialize=initialize,
            strategy_params=strategy_params
        )
    except KeyboardInterrupt:
        print("\n用户中断")
        runner.stop()
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()
        runner.stop()

