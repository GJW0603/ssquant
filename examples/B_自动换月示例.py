"""
自动换月 + 双均线示例（SIMNOW / 实盘）

功能说明：
  当主力合约发生切换时，框架自动帮你完成移仓（平旧合约 → 开新主力），无需在策略里手写。
  只需在 get_config 中设置 auto_roll_enabled=True 即可开启。

  移仓模式：
    'simultaneous' — 同时发出平旧和开新委托（更快）
    'sequential'   — 先平旧，确认平完后再开新（更稳）

本策略示例只做两件事：
  1. 双均线交易信号
  2. 移仓进行中时暂停下单（api.is_rollover_busy()），避免与移仓冲突

回测模式下不执行自动移仓，本示例等价于普通双均线策略。
"""

from ssquant.api.strategy_api import StrategyAPI
from ssquant.backtest.unified_runner import UnifiedStrategyRunner, RunMode
from ssquant.config.trading_config import get_config


def initialize(api: StrategyAPI):
    api.log("=" * 50)
    api.log("框架内自动换月 + 双均线 — 初始化")
    api.log("=" * 50)
    fast_ma = api.get_param("fast_ma", 5)
    slow_ma = api.get_param("slow_ma", 20)
    api.log(f"均线参数: fast_ma={fast_ma}, slow_ma={slow_ma}")
    api.log(
        "移仓：由适配器在策略前调用 RolloverEngine；请在 get_config 中设置 "
        "auto_roll_enabled=True 及 auto_roll_mode / auto_roll_reopen 等（见本文件配置区）。"
    )


def rollover_ma_strategy(api: StrategyAPI):
    """双均线；移仓进行中不下新单。"""
    fast_ma = api.get_param("fast_ma", 5)
    slow_ma = api.get_param("slow_ma", 20)
    pause_on_roll = api.get_param("pause_signals_when_rollover_busy", True)

    if pause_on_roll and api.is_rollover_busy():
        return

    ds = api.get_data_source(0)
    current_idx = api.get_idx(0)
    if current_idx < slow_ma:
        return

    close = api.get_close(0)
    if len(close) < slow_ma:
        return

    fast_ma_values = close.rolling(fast_ma).mean()
    slow_ma_values = close.rolling(slow_ma).mean()

    current_pos = api.get_pos(0)

    if fast_ma_values.iloc[-2] <= slow_ma_values.iloc[-2] and fast_ma_values.iloc[-1] > slow_ma_values.iloc[-1]:
        if current_pos <= 0:
            if current_pos < 0:
                api.buycover(volume=1, order_type="next_bar_open", index=0)
            api.buy(volume=1, order_type="next_bar_open", index=0)
            api.log(f"均线金叉：买入（{getattr(ds, 'symbol', '')}）")

    elif fast_ma_values.iloc[-2] >= slow_ma_values.iloc[-2] and fast_ma_values.iloc[-1] < slow_ma_values.iloc[-1]:
        if current_pos >= 0:
            if current_pos > 0:
                api.sell(order_type="next_bar_open", index=0)
            api.sellshort(volume=1, order_type="next_bar_open", index=0)
            api.log(f"均线死叉：做空（{getattr(ds, 'symbol', '')}）")


# =====================================================================
# 配置区（修改 RUN_MODE 与对应的 get_config 参数即可）
# =====================================================================

if __name__ == "__main__":

    RUN_MODE = RunMode.SIMNOW

    strategy_params = {
        "fast_ma": 5,
        "slow_ma": 20,
        # 为 True 时，api.is_rollover_busy() 期间不发出均线信号（推荐）
        "pause_signals_when_rollover_busy": True,
    }

    # --- 回测：不包含 auto_roll_*（回测不跑框架移仓）---
    if RUN_MODE == RunMode.BACKTEST:
        config = get_config(
            RUN_MODE,
            symbol="au888",
            start_date="2025-12-01",
            end_date="2026-01-31",
            kline_period="15m",
            adjust_type="1",
            debug=False,
            initial_capital=500000,
            slippage_ticks=1,
            lookback_bars=500,
        )

    elif RUN_MODE == RunMode.SIMNOW:
        config = get_config(
            RUN_MODE,
            account="simnow_default",
            server_name="电信1",
            symbol="au888",
            kline_period="1m",
            order_offset_ticks=-5,
            algo_trading=False,
            order_timeout=10,
            retry_limit=3,
            retry_offset_ticks=5,
            preload_history=True,
            history_lookback_bars=5000,
            adjust_type="1",
            lookback_bars=1000,
            enable_tick_callback=False,
            save_kline_csv=True,
            save_kline_db=True,
            save_tick_csv=False,
            save_tick_db=False,
            # -------- 自动移仓（主力合约换月）--------
            # 开启后，当主力合约发生切换时，框架自动帮你：平掉旧主力仓位 → 在新主力上重新开仓
            # 策略中可用 api.is_rollover_busy() 判断移仓是否进行中，避免与移仓抢单
            auto_roll_enabled=True,            # 是否启用自动移仓
            auto_roll_mode="simultaneous",     # 'simultaneous'=同时平开（更快）  'sequential'=先平后开（更稳）
            auto_roll_reopen=True,             # 平旧仓后是否在新主力上补开仓位
            auto_roll_order_type="next_bar_open",  # 移仓委托方式
            auto_roll_close_offset_ticks=None, # 平旧跳数偏移（None=沿用 order_offset_ticks）
            auto_roll_open_offset_ticks=None,  # 开新跳数偏移（None=沿用 order_offset_ticks）
            auto_roll_verify_timeout_bars=500, # 超时重置（策略回调次数）
            auto_roll_log_enabled=True,        # 记录移仓日志
        )

    elif RUN_MODE == RunMode.REAL_TRADING:
        config = get_config(
            RUN_MODE,
            account="real_default",
            symbol="au888",
            kline_period="1m",
            order_offset_ticks=-10,
            algo_trading=True,
            order_timeout=10,
            retry_limit=3,
            retry_offset_ticks=5,
            preload_history=True,
            history_lookback_bars=5000,
            adjust_type="1",
            lookback_bars=500,
            enable_tick_callback=False,
            save_kline_csv=False,
            save_kline_db=False,
            save_tick_csv=False,
            save_tick_db=False,
            # -------- 自动移仓（主力合约换月）--------
            # 开启后，主力切换时自动 平旧→开新，免去手动换月
            # 策略中可用 api.is_rollover_busy() 判断移仓是否进行中
            auto_roll_enabled=True,            # 是否启用自动移仓
            auto_roll_mode="sequential",       # 'simultaneous'=同时平开  'sequential'=先平后开（实盘更稳）
            auto_roll_reopen=True,             # 平旧仓后是否在新主力上补开仓位
            auto_roll_order_type="next_bar_open",  # 移仓委托方式
            auto_roll_close_offset_ticks=None, # 平旧跳数偏移（None=沿用 order_offset_ticks）
            auto_roll_open_offset_ticks=None,  # 开新跳数偏移（None=沿用 order_offset_ticks）
            auto_roll_verify_timeout_bars=500, # 超时重置（策略回调次数）
            auto_roll_log_enabled=True,        # 记录移仓日志
        )

    print("\n" + "=" * 80)
    print("框架内自动换月 + 双均线 (B_自动换月示例.py)")
    print("=" * 80)
    print(f"运行模式: {RUN_MODE.value}")
    if "data_sources" in config:
        data_sources_info = [f"{ds['symbol']}_{ds['kline_period']}" for ds in config["data_sources"]]
        print(f"数据源: {', '.join(data_sources_info)}")
    else:
        print(f"合约代码: {config['symbol']}")
    print(f"策略参数: {strategy_params}")
    if RUN_MODE in (RunMode.SIMNOW, RunMode.REAL_TRADING):
        print(
            "框架移仓: "
            f"enabled={config.get('auto_roll_enabled')}, "
            f"mode={config.get('auto_roll_mode')}, "
            f"reopen={config.get('auto_roll_reopen')}"
        )
    print("自动获取的合约参数:")
    print(f"  合约乘数: {config.get('contract_multiplier', '未设置')}")
    print(f"  最小跳动: {config.get('price_tick', '未设置')}")
    print(f"  保证金率: {config.get('margin_rate', '未设置')}")
    print(f"  手续费率: {config.get('commission', '未设置')}")
    print("=" * 80 + "\n")

    runner = UnifiedStrategyRunner(mode=RUN_MODE)
    runner.set_config(config)

    try:
        runner.run(
            strategy=rollover_ma_strategy,
            initialize=initialize,
            strategy_params=strategy_params,
        )
    except KeyboardInterrupt:
        print("\n用户中断")
        runner.stop()
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback

        traceback.print_exc()
        runner.stop()
