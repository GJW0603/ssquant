"""
期货期权组合交易示例 - SSQuant框架版

展示期货与期权的组合交易策略测试：
1. 保护性看跌（Protective Put）：期货多头 + 买入看跌期权
2. 备兑看涨（Covered Call）：期货多头 + 卖出看涨期权
3. 领口策略（Collar）：期货多头 + 买看跌 + 卖看涨

数据源配置：
    index=0: 看涨期权
    index=1: 看跌期权
    index=2: 标的期货

支持模式：SIMNOW模拟 / 实盘CTP
"""

import time
from datetime import datetime

from ssquant.api.strategy_api import StrategyAPI
from ssquant.backtest.unified_runner import UnifiedStrategyRunner, RunMode
from ssquant.config.trading_config import get_config


# ========== 合约配置 ==========
CALL_OPTION = 'au2602C650'      # 看涨期权
PUT_OPTION = 'au2602P640'       # 看跌期权
UNDERLYING = 'au2602'           # 标的期货

VOLUME = 1                      # 交易手数
INTERVAL = 3.0                  # 操作间隔（秒）

# ========== 数据源索引 ==========
IDX_CALL = 0
IDX_PUT = 1
IDX_FUTURE = 2

# ========== 测试状态（状态机） ==========
# g_phase 可选值:
#   - 'wait_price':     等待行情就绪
#   - 'pp_buy_future':  策略1-买期货    'pp_buy_put':  策略1-买看跌
#   - 'pp_close_put':   策略1-平看跌    'pp_close_fut': 策略1-平期货
#   - 'cc_buy_future':  策略2-买期货    'cc_sell_call': 策略2-卖看涨
#   - 'cc_cover_call':  策略2-平看涨    'cc_close_fut': 策略2-平期货
#   - 'collar_buy_fut': 策略3-买期货    'collar_buy_put': 策略3-买看跌
#   - 'collar_sell_call': 策略3-卖看涨  'collar_close': 策略3-平仓
#   - 'done'/'finished': 测试完成
# 可修改初始值跳过前面步骤，如: g_phase = 'cc_buy_future'
g_phase = 'pp_buy_future'
g_waiting = False                                    # 订单等待标志
g_prices = {'call': 0, 'put': 0, 'future': 0}       # 实时价格缓存
g_stats = {'trades': 0}                              # 交易统计


def on_trade(data):
    """成交回调"""
    global g_waiting, g_stats
    g_waiting = False
    g_stats['trades'] += 1
    
    inst = data['InstrumentID']
    d = '买' if data['Direction'] == '0' else '卖'
    o = '开' if data['OffsetFlag'] == '0' else '平'
    
    if 'C' in inst:
        t = "看涨期权"
    elif 'P' in inst:
        t = "看跌期权"
    else:
        t = "期货"
    
    print(f"✅ [{t}成交] {inst} {d}{o} 价格:{data['Price']:.2f} 数量:{data['Volume']}")


def on_order(data):
    """报单回调"""
    status = {'0': '成交', '3': '未成交', '5': '已撤'}
    d = '买' if data.get('Direction') == '0' else '卖'
    print(f"📋 [报单] {data['InstrumentID']} {d} {status.get(data['OrderStatus'], '?')}")


def on_order_error(data):
    """报单错误"""
    global g_waiting
    g_waiting = False
    print(f"❌ [错误] {data['ErrorID']}: {data['ErrorMsg']}")


def on_position(data):
    """持仓回调"""
    inst = data['InstrumentID']
    pos = data.get('Position', 0)
    direction = {'2': '多', '3': '空'}.get(data.get('PosiDirection'), '')
    if pos > 0:
        print(f"📊 [持仓] {inst} {direction} {pos}手")


def initialize(api: StrategyAPI):
    """初始化"""
    print(f"\n{'='*60}")
    print(f"期货期权组合交易测试")
    print(f"{'='*60}")
    print(f"看涨期权: {CALL_OPTION} (index=0)")
    print(f"看跌期权: {PUT_OPTION} (index=1)")
    print(f"标的期货: {UNDERLYING} (index=2)")
    print(f"{'='*60}")
    print(f"\n测试策略:")
    print(f"  1. 保护性看跌: 期货多头 + 买入看跌期权")
    print(f"  2. 备兑看涨: 期货多头 + 卖出看涨期权")
    print(f"  3. 领口策略: 期货多头 + 买看跌 + 卖看涨")
    print(f"{'='*60}\n")


def strategy(api: StrategyAPI):
    """期货期权组合策略"""
    global g_phase, g_waiting, g_prices, g_tick_count
    
    # 初始化计数器
    if 'g_tick_count' not in dir():
        g_tick_count = 0
    
    tick = api.get_tick()
    if tick is None:
        return
    
    inst = tick.get('InstrumentID', '')
    price = tick.get('LastPrice', 0)
    bid = tick.get('BidPrice1', 0)
    ask = tick.get('AskPrice1', 0)
    vol = tick.get('Volume', 0)
    time_str = tick.get('UpdateTime', '')
    
    # 更新价格
    if inst == CALL_OPTION:
        g_prices['call'] = price
    elif inst == PUT_OPTION:
        g_prices['put'] = price
    elif inst == UNDERLYING:
        g_prices['future'] = price
    
    # 输出行情数据（每10个TICK输出一次，避免刷屏）
    g_tick_count = getattr(strategy, 'tick_count', 0) + 1
    strategy.tick_count = g_tick_count
    
    if g_tick_count % 10 == 1:  # 第1, 11, 21... 个TICK输出
        print(f"\n[{time_str}] 行情更新 (第{g_tick_count}个TICK)")
        print(f"  {inst}: 最新:{price:.2f} 买一:{bid:.2f} 卖一:{ask:.2f} 成交量:{vol}")
        print(f"  汇总 - 期货:{g_prices['future']:.2f} | 看涨:{g_prices['call']:.2f} | 看跌:{g_prices['put']:.2f}")
    
    if g_waiting:
        return
    
    call_pos = api.get_pos(index=IDX_CALL)
    put_pos = api.get_pos(index=IDX_PUT)
    fut_pos = api.get_pos(index=IDX_FUTURE)
    
    # 等待价格就绪
    if g_phase == 'wait_price':
        if g_prices['call'] > 0 and g_prices['put'] > 0 and g_prices['future'] > 0:
            print(f"\n>>> 价格就绪")
            print(f"    期货:{g_prices['future']:.2f} | 看涨:{g_prices['call']:.2f} | 看跌:{g_prices['put']:.2f}")
            g_phase = 'pp_buy_future'
            time.sleep(1)
        return
    
    # ==================== 策略1: 保护性看跌 ====================
    if g_phase == 'pp_buy_future':
        print(f"\n{'#'*60}")
        print(f"# 策略1: 保护性看跌（Protective Put）")
        print(f"{'#'*60}")
        print(f"\n>>> 步骤1: 买入期货")
        api.buy(volume=VOLUME, order_type='market', reason='保护性看跌-买期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'pp_buy_put', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'pp_buy_put' and fut_pos > 0:
        print(f">>> 步骤2: 买入看跌期权")
        api.buy(volume=VOLUME, order_type='market', reason='保护性看跌-买看跌', index=IDX_PUT)
        g_phase, g_waiting = 'pp_close_put', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'pp_close_put' and put_pos > 0:
        print(f">>> 步骤3: 平仓看跌期权")
        api.sell(order_type='market', reason='平仓看跌', index=IDX_PUT)
        g_phase, g_waiting = 'pp_close_fut', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'pp_close_fut' and put_pos == 0 and fut_pos > 0:
        print(f">>> 步骤4: 平仓期货")
        api.sell(order_type='market', reason='平仓期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'cc_buy_future', True
        time.sleep(INTERVAL)
        return
    
    # ==================== 策略2: 备兑看涨 ====================
    if g_phase == 'cc_buy_future' and fut_pos == 0:
        print(f"\n{'#'*60}")
        print(f"# 策略2: 备兑看涨（Covered Call）")
        print(f"{'#'*60}")
        print(f"\n>>> 步骤1: 买入期货")
        api.buy(volume=VOLUME, order_type='market', reason='备兑看涨-买期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'cc_sell_call', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'cc_sell_call' and fut_pos > 0:
        # 检查期权价格是否有效（流动性差时买一价可能为0）
        if g_prices['call'] <= 0:
            print(f"⚠️ 看涨期权价格为0，跳过卖出，直接平仓期货")
            g_phase = 'cc_close_fut'
            return
        print(f">>> 步骤2: 卖出看涨期权 (当前价:{g_prices['call']:.2f})")
        api.sellshort(volume=VOLUME, order_type='market', reason='备兑看涨-卖看涨', index=IDX_CALL)
        g_phase, g_waiting = 'cc_cover_call', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'cc_cover_call' and call_pos < 0:
        print(f">>> 步骤3: 平仓看涨期权空头")
        api.buycover(order_type='market', reason='平仓看涨空头', index=IDX_CALL)
        g_phase, g_waiting = 'cc_close_fut', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'cc_close_fut' and call_pos == 0 and fut_pos > 0:
        print(f">>> 步骤4: 平仓期货")
        api.sell(order_type='market', reason='平仓期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'collar_buy_fut', True
        time.sleep(INTERVAL)
        return
    
    # ==================== 策略3: 领口策略 ====================
    if g_phase == 'collar_buy_fut' and fut_pos == 0:
        print(f"\n{'#'*60}")
        print(f"# 策略3: 领口策略（Collar）")
        print(f"{'#'*60}")
        print(f"\n>>> 步骤1: 买入期货")
        api.buy(volume=VOLUME, order_type='market', reason='领口-买期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'collar_buy_put', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'collar_buy_put' and fut_pos > 0:
        print(f">>> 步骤2: 买入看跌期权")
        api.buy(volume=VOLUME, order_type='market', reason='领口-买看跌', index=IDX_PUT)
        g_phase, g_waiting = 'collar_sell_call', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'collar_sell_call' and put_pos > 0:
        # 检查期权价格是否有效
        if g_prices['call'] <= 0:
            print(f"⚠️ 看涨期权价格为0，跳过卖出，直接平仓")
            g_phase = 'collar_close2'
            return
        print(f">>> 步骤3: 卖出看涨期权 (当前价:{g_prices['call']:.2f})")
        api.sellshort(volume=VOLUME, order_type='market', reason='领口-卖看涨', index=IDX_CALL)
        g_phase, g_waiting = 'collar_close', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'collar_close' and call_pos < 0:
        print(f"\n>>> 领口组合建立完成，开始平仓...")
        print(f">>> 步骤4: 平仓看涨期权空头")
        api.buycover(order_type='market', reason='平仓看涨空头', index=IDX_CALL)
        g_phase, g_waiting = 'collar_close2', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'collar_close2' and call_pos == 0:
        print(f">>> 步骤5: 平仓看跌期权多头")
        api.sell(order_type='market', reason='平仓看跌多头', index=IDX_PUT)
        g_phase, g_waiting = 'collar_close3', True
        time.sleep(INTERVAL)
        return
    
    if g_phase == 'collar_close3' and put_pos == 0:
        print(f">>> 步骤6: 平仓期货多头")
        api.sell(order_type='market', reason='平仓期货', index=IDX_FUTURE)
        g_phase, g_waiting = 'done', True
        time.sleep(INTERVAL)
        return
    
    # 测试完成
    if g_phase == 'done':
        print(f"\n{'='*60}")
        print(f"期货期权组合交易测试完成")
        print(f"{'='*60}")
        print(f"总成交: {g_stats['trades']}笔")
        print(f"\n测试策略汇总:")
        print(f"  ✓ 保护性看跌: 期货多头 + 买入看跌期权")
        print(f"  ✓ 备兑看涨: 期货多头 + 卖出看涨期权")
        print(f"  ✓ 领口策略: 期货多头 + 买看跌 + 卖看涨")
        print(f"{'='*60}")
        print(f"\n按 Ctrl+C 退出\n")
        g_phase = 'finished'


if __name__ == "__main__":
    
    # ==================== 运行模式选择 ====================
    RUN_MODE = RunMode.SIMNOW      # SIMNOW 或 REAL_TRADING
    
    # ==================== 配置 ====================
    if RUN_MODE == RunMode.SIMNOW:
        # ==================== SIMNOW模拟盘配置 ====================
        config = get_config(RUN_MODE,
            # -------- 账户配置 --------
            # account: 账户名称，需要在 trading_config.py 的 ACCOUNTS 字典中定义
            #          包含 broker_id, investor_id, password 等信息
            # server_name: SIMNOW服务器选择
            #   - '电信1': 交易时段使用，行情稳定
            #   - '电信2': 交易时段使用，备用服务器
            #   - '移动':  移动网络用户
            #   - 'TEST':  盘后测试（7x24小时），非交易时段测试用
            account='simnow_default',
            server_name='电信1',
            
            # -------- 多数据源配置 --------
            # data_sources: 多品种订阅配置，每个元素对应一个数据源
            #   - symbol:      合约代码
            #   - kline_period: K线周期 (1m/5m/15m/30m/1h/1d)
            #   - price_tick:  最小变动价位 (黄金期权=0.02)
            # 
            # 使用方式:
            #   - 通过 index 参数指定操作哪个品种
            #   - api.buy(index=0)  -> 买入 index=0 的品种（看涨期权）
            #   - api.sell(index=1) -> 卖出 index=1 的品种（看跌期权）
            #   - api.get_pos(index=2) -> 获取 index=2 的持仓（期货）
            data_sources=[
                {'symbol': CALL_OPTION, 'kline_period': '1m', 'price_tick': 0.02},  # index=0 看涨期权
                {'symbol': PUT_OPTION, 'kline_period': '1m', 'price_tick': 0.02},   # index=1 看跌期权
                {'symbol': UNDERLYING, 'kline_period': '1m', 'price_tick': 0.02},   # index=2 标的期货
            ],
            
            # -------- 交易参数 --------
            # order_offset_ticks: 委托价格偏移跳数
            #   - 买入时: 委托价 = 卖一价 + offset_ticks * price_tick (超价买入)
            #   - 卖出时: 委托价 = 买一价 - offset_ticks * price_tick (超价卖出)
            #   - ⚠️ 期权价格可能很低（接近0），设为0直接使用买一/卖一价
            order_offset_ticks=0,          # 期权价格低，使用0避免负价格
            
            # -------- 智能算法交易配置 --------
            # 功能：超时未成交自动撤单 → 按超价重新下单，最多重试N次
            algo_trading=True,            # 启用算法交易
            order_timeout=10,             # 订单超时时间(秒)
            retry_limit=3,                # 最大重试次数
            retry_offset_ticks=2,         # 重试时的超价跳数
            
            # -------- 回调模式 --------
            # enable_tick_callback: 策略触发方式
            #   - True:  每收到一个TICK就触发策略函数（高频交易、实时监控）
            #   - False: 每根K线完成时触发策略函数（趋势策略、低频交易）
            # preload_history: 是否预加载历史K线数据
            #   - True:  启动时加载历史数据，用于计算指标
            #   - False: 不加载历史数据，适合纯TICK驱动策略
            enable_tick_callback=True,
            preload_history=False,
            
            # -------- 数据保存 --------
            # 将实时数据保存到本地，便于后续分析
            save_kline_csv=False,          # 保存K线到CSV (路径: ./live_data/)
            save_kline_db=False,           # 保存K线到SQLite数据库
            save_tick_csv=False,           # 保存TICK到CSV
            save_tick_db=False,            # 保存TICK到数据库
        )
    
    elif RUN_MODE == RunMode.REAL_TRADING:
        # ==================== 实盘CTP配置 ====================
        config = get_config(RUN_MODE,
            # -------- 账户配置 --------
            # 实盘账户需要在 trading_config.py 中配置以下信息:
            #   - broker_id:   期货公司代码（如 '9999'）
            #   - investor_id: 资金账号
            #   - password:    交易密码
            #   - md_server:   行情服务器地址 (如 'tcp://180.168.146.187:10211')
            #   - td_server:   交易服务器地址 (如 'tcp://180.168.146.187:10201')
            #   - app_id:      应用ID（穿透式监管）
            #   - auth_code:   授权码（穿透式监管）
            account='real_default',
            
            # -------- 多数据源配置 --------
            data_sources=[
                {'symbol': CALL_OPTION, 'kline_period': '1m', 'price_tick': 0.02},  # index=0 看涨期权
                {'symbol': PUT_OPTION, 'kline_period': '1m', 'price_tick': 0.02},   # index=1 看跌期权
                {'symbol': UNDERLYING, 'kline_period': '1m', 'price_tick': 0.02},   # index=2 标的期货
            ],
            
            # -------- 交易参数 --------
            order_offset_ticks=0,          # 期权价格低，使用0避免负价格
            
            # -------- 智能算法交易配置 --------
            # 功能：超时未成交自动撤单 → 按超价重新下单，最多重试N次
            algo_trading=True,            # 启用算法交易
            order_timeout=10,             # 订单超时时间(秒)
            retry_limit=3,                # 最大重试次数
            retry_offset_ticks=5,         # 重试时的超价跳数
            
            # -------- 回调模式 --------
            enable_tick_callback=True,
            preload_history=False,
            
            # -------- 数据保存 --------
            save_kline_csv=False,
            save_kline_db=False,
            save_tick_csv=False,
            save_tick_db=False,
        )
    
    # ==================== 运行 ====================
    print(f"\n运行模式: {RUN_MODE.value}")
    
    runner = UnifiedStrategyRunner(mode=RUN_MODE)
    runner.set_config(config)
    
    try:
        runner.run(
            strategy=strategy,
            initialize=initialize,
            on_trade=on_trade,
            on_order=on_order,
            on_order_error=on_order_error,
            on_position=on_position,
        )
    except KeyboardInterrupt:
        print(f"\n{'='*40}")
        print(f"【最终行情】")
        print(f"  期货 {UNDERLYING}: {g_prices['future']:.2f}")
        print(f"  看涨 {CALL_OPTION}: {g_prices['call']:.2f}")
        print(f"  看跌 {PUT_OPTION}: {g_prices['put']:.2f}")
        print(f"{'='*40}")
        runner.stop()
