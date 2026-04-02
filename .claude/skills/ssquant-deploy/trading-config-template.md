# 交易配置模板

## SIMNOW 仿真配置模板

```python
from ssquant.config.trading_config import get_config, RunMode

PARAMS = {
    # 策略参数
}

config = get_config(
    RunMode.SIMNOW,
    account="simnow_default",

    # === 合约 ===
    symbol="rb2510",
    kline_period="1m",

    # === SIMNOW 认证 ===
    investor_id="你的SIMNOW账号",
    password="你的SIMNOW密码",
    server_name="电信1",

    # === 数据 ===
    preload_history=True,
    history_lookback_bars=200,
    lookback_bars=0,
    adjust_type="1",

    # === 交易 ===
    order_offset_ticks=2,
    algo_trading=False,
    order_timeout=30,
    retry_limit=3,
    retry_offset_ticks=1,

    # === Tick ===
    enable_tick_callback=False,
    tick_callback_interval=0.5,
    tick_queue_maxsize=20000,

    # === 策略参数 ===
    auto_params=True,
    params=PARAMS,
)
```

## 实盘配置模板

```python
config = get_config(
    RunMode.REAL_TRADING,
    account="real_default",

    # === 合约 ===
    symbol="rb2510",
    kline_period="1m",

    # === 期货公司认证 ===
    broker_id="期货公司代码",
    investor_id="资金账号",
    password="交易密码",
    md_server="tcp://行情前置:端口",
    td_server="tcp://交易前置:端口",
    app_id="穿透式AppID",
    auth_code="穿透式AuthCode",

    # === 数据 ===
    preload_history=True,
    history_lookback_bars=200,
    adjust_type="1",

    # === 交易 ===
    order_offset_ticks=2,
    algo_trading=False,
    order_timeout=30,
    retry_limit=3,

    # === 自动移仓 ===
    auto_roll_enabled=False,
    auto_roll_mode="simultaneous",
    auto_roll_reopen=True,
    auto_roll_close_offset_ticks=2,
    auto_roll_open_offset_ticks=2,
    auto_roll_verify_timeout_bars=10,
    auto_roll_log_enabled=True,

    # === 数据持久化 ===
    save_kline_csv=True,
    save_tick_csv=False,
    data_save_path="live_data",

    # === 策略参数 ===
    auto_params=True,
    params=PARAMS,
)
```

## data_server 模式配置模板

```python
config = get_config(
    RunMode.SIMNOW,
    account="simnow_default",

    symbol="rb2510",
    kline_period="1m",
    kline_source="data_server",       # 远程 K 线推送

    investor_id="你的SIMNOW账号",
    password="你的SIMNOW密码",
    server_name="电信1",

    enable_tick_callback=True,
    tick_callback_interval=0.5,       # 防开盘洪峰
    tick_queue_maxsize=20000,

    preload_history=True,
    history_lookback_bars=200,
    adjust_type="1",

    auto_params=True,
    params=PARAMS,
)
```

## 自动移仓配置模板

```python
config = get_config(
    RunMode.SIMNOW,
    account="simnow_default",

    symbol="rb2510",
    kline_period="1m",

    auto_roll_enabled=True,
    auto_roll_mode="simultaneous",    # simultaneous / sequential
    auto_roll_reopen=True,            # 移仓后自动重新开仓
    auto_roll_order_type="limit",
    auto_roll_close_offset_ticks=2,
    auto_roll_open_offset_ticks=2,
    auto_roll_verify_timeout_bars=10,
    auto_roll_log_enabled=True,
    auto_roll_log_jsonl=False,

    # ...其他参数
)
```
