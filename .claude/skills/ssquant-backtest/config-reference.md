# TradingConfig 完整配置参考

> 来源: `ssquant/config/trading_config.py`

## 配置加载方式

```python
from ssquant.config.trading_config import get_config, RunMode

config = get_config(
    mode=RunMode.BACKTEST,   # BACKTEST / SIMNOW / REAL_TRADING
    account=None,            # 账户名（仿真/实盘用）
    auto_params=True,        # 自动填充合约参数
    **overrides              # 任意覆盖参数
)
```

## 回测默认值 (BACKTEST_DEFAULTS)

| 键 | 默认值 | 类型 | 说明 |
|----|--------|------|------|
| `initial_capital` | `20000` | int | 初始资金（元） |
| `commission` | `0.0001` | float | 手续费率 |
| `margin_rate` | `0.1` | float | 保证金率 |
| `contract_multiplier` | `10` | int | 合约乘数 |
| `price_tick` | `1.0` | float | 最小变动价位 |
| `slippage_ticks` | `1` | int | 滑点 tick 数 |
| `adjust_type` | `'1'` | str | `'0'`不复权 / `'1'`后复权 / `'2'`前复权 |
| `align_data` | `False` | bool | 多品种时间对齐 |
| `fill_method` | `'ffill'` | str | 对齐填充方式 |
| `lookback_bars` | `0` | int | K线回溯窗口（0=不限） |
| `use_cache` | `True` | bool | 使用本地缓存 |
| `save_data` | `True` | bool | 保存获取的数据 |
| `debug` | `False` | bool | 调试日志 |
| `tick_queue_maxsize` | `20000` | int | Tick 队列上限 |

## SIMNOW 账户默认配置 (simnow_default)

### 认证

| 键 | 说明 |
|----|------|
| `investor_id` | SIMNOW 账号 |
| `password` | SIMNOW 密码 |
| `server_name` | 服务器名：`电信1` / `电信2` / `移动` / `TEST` / `24hour` |

### 交易参数

| 键 | 默认值 | 说明 |
|----|--------|------|
| `kline_period` | `"1m"` | K线周期 |
| `price_tick` | `1.0` | 最小变动价位 |
| `order_offset_ticks` | `2` | 下单偏移 tick |
| `algo_trading` | `False` | 算法交易模式 |
| `order_timeout` | `30` | 订单超时秒数 |
| `retry_limit` | `3` | 撤单重发次数 |
| `retry_offset_ticks` | `1` | 重发偏移 tick |

### 数据参数

| 键 | 默认值 | 说明 |
|----|--------|------|
| `preload_history` | `True` | 预加载历史 K 线 |
| `history_lookback_bars` | `200` | 预加载条数 |
| `lookback_bars` | `0` | 运行时回溯（0=不限） |
| `adjust_type` | `'1'` | 复权类型 |
| `kline_source` | `None` | `None`=CTP / `'data_server'`=远程推送 |
| `history_symbol` | `None` | 历史数据使用的合约（可选） |

### Tick 参数

| 键 | 默认值 | 说明 |
|----|--------|------|
| `enable_tick_callback` | `False` | 启用 Tick 回调 |
| `tick_callback_interval` | `0.5` | Tick 回调最小间隔（秒） |
| `tick_queue_maxsize` | `20000` | Tick 队列上限 |

### 自动移仓参数

| 键 | 默认值 | 说明 |
|----|--------|------|
| `auto_roll_enabled` | `False` | 启用自动移仓 |
| `auto_roll_mode` | `"simultaneous"` | `simultaneous` / `sequential` |
| `auto_roll_reopen` | `True` | 移仓后自动重新开仓 |
| `auto_roll_order_type` | `"limit"` | 移仓订单类型 |
| `auto_roll_close_offset_ticks` | `2` | 平仓偏移 tick |
| `auto_roll_open_offset_ticks` | `2` | 开仓偏移 tick |
| `auto_roll_verify_timeout_bars` | `10` | 移仓验证超时 bar 数 |
| `auto_roll_log_enabled` | `True` | 记录移仓审计日志 |
| `auto_roll_log_dir` | `""` | 日志目录（空=默认） |
| `auto_roll_log_jsonl` | `False` | 同时输出 JSONL |

### 数据持久化

| 键 | 默认值 | 说明 |
|----|--------|------|
| `save_kline_csv` | `False` | 保存 K 线到 CSV |
| `save_kline_db` | `False` | 保存 K 线到 SQLite |
| `save_tick_csv` | `False` | 保存 Tick 到 CSV |
| `save_tick_db` | `False` | 保存 Tick 到 SQLite |
| `data_save_path` | `"live_data"` | 数据保存根目录 |
| `db_path` | `""` | 数据库路径 |

## 实盘账户配置 (real_default)

在 SIMNOW 基础上额外需要：

| 键 | 说明 |
|----|------|
| `broker_id` | 期货公司代码 |
| `investor_id` | 资金账号 |
| `password` | 交易密码 |
| `md_server` | 行情前置地址 |
| `td_server` | 交易前置地址 |
| `app_id` | 穿透式认证 AppID |
| `auth_code` | 穿透式认证 AuthCode |

## 全局认证

| 变量 | 说明 |
|------|------|
| `API_USERNAME` | 数据服务认证用户名 |
| `API_PASSWORD` | 数据服务认证密码 |
| `ENABLE_REMOTE_ADJUST` | 启用远程复权数据（默认 True） |

## data_server 配置

当 `kline_source='data_server'` 时，自动合并 `DATA_SERVER` 配置：

```python
config = get_config(
    RunMode.SIMNOW,
    account="simnow_default",
    symbol="rb2510",
    kline_period="1m",
    kline_source="data_server",  # 启用远程推送
    enable_tick_callback=True,
    tick_callback_interval=0.5,
)
```

data_server 模式下服务器推送任意周期 K 线 + 订单流数据，无需本地聚合。
