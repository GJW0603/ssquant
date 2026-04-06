# StrategyAPI 完整方法参考

> 来源: `ssquant/api/strategy_api.py`  
> **v0.4.4**：`get_account` / `get_balance` / `get_available` / `get_position_profit` / `get_close_profit` / `get_margin` / `get_commission` 在**回测、SIMNOW、实盘**均可用（文档注释已与行为对齐）。

## 构造

```python
from ssquant.api.strategy_api import StrategyAPI, create_strategy_api
api = create_strategy_api(context)  # 框架内部调用，用户不直接构造
```

## 行情数据方法

### get_klines(index=0, window=None) -> pd.DataFrame

获取 K 线数据。

- `index`: 数据源索引（多品种时 0, 1, 2...）
- `window`: 返回的最近 K 线条数。`None` 使用配置的 `lookback_bars`，`0` 返回全部。
- 返回列: `open, high, low, close, volume`，以及 data_server 模式下可能的订单流列

### get_price(index=0) -> Optional[float]

当前价格（复权后）。data_server + 本地复权模式下返回调整后价格。

### get_raw_price(index=0) -> Optional[float]

原始未复权价格。仅在 data_server 模式 + 启用本地复权时与 `get_price` 不同。

### get_close(index=0) -> pd.Series
### get_open(index=0) -> pd.Series
### get_high(index=0) -> pd.Series
### get_low(index=0) -> pd.Series
### get_volume(index=0) -> pd.Series

返回对应 OHLCV 的 pandas Series。

### get_datetime(index=0)

当前 K 线的 datetime 对象。

### get_idx(index=0) -> int

当前 K 线的整数索引（从 0 开始），无效时返回 -1。

### get_tick(index=0) -> pd.Series

当前 Tick 快照。字段包括 `last_price, volume, open_interest, bid_price1, ask_price1, bid_volume1, ask_volume1` 等。

### get_ticks(window=None, index=0) -> pd.DataFrame

最近 N 条 Tick 数据。

### get_ticks_count(index=0) -> int

已缓存的 Tick 数量。

## 持仓方法

### get_pos(index=0) -> int

净持仓 = 多头 - 空头。

### get_long_pos(index=0) -> int

多头持仓手数。

### get_short_pos(index=0) -> int

空头持仓手数。

### get_position_detail(index=0) -> dict

```python
{
    "net_pos": 1,
    "long_pos": 1, "short_pos": 0,
    "long_today": 0, "long_yd": 1,
    "short_today": 0, "short_yd": 0
}
```

## 下单方法

### buy(volume=1, reason="", order_type='bar_close', index=0, offset_ticks=None, price=None)

开多仓。

- `volume`: 手数
- `reason`: 交易原因（记录到日志）
- `order_type`: `'bar_close'` | `'next_bar_open'` | `'limit'` | `'market'`
- `offset_ticks`: 限价单偏移 tick 数
- `price`: 精确限价（优先于 offset_ticks）

### sell(volume=None, reason="", order_type='bar_close', index=0, offset_ticks=None, price=None)

平多仓。`volume=None` 时全部平仓。

### sellshort(volume=1, reason="", order_type='bar_close', index=0, offset_ticks=None, price=None)

开空仓。

### buycover(volume=None, reason="", order_type='bar_close', index=0, offset_ticks=None, price=None)

平空仓。`volume=None` 时全部平仓。`buytocover` 是别名。

### close_all(reason="", order_type='bar_close', index=0)

平掉所有多空持仓。

### reverse_pos(reason="", order_type='bar_close', index=0)

反手：平掉当前持仓并开反向等量仓位。

### cancel_all_orders(index=0)

撤销所有挂单（仅实盘有效，回测中无操作）。

## 账户资金方法

### get_account() -> dict

```python
{
    "balance": 100000.0,        # 动态权益
    "available": 80000.0,       # 可用资金
    "position_profit": 500.0,   # 持仓盈亏
    "close_profit": 200.0,      # 平仓盈亏
    "commission": 50.0,         # 手续费
    "frozen_margin": 0.0,       # 冻结保证金
    "curr_margin": 10000.0,     # 当前保证金
    "update_time": "14:30:00"   # 更新时间
}
```

### get_balance() -> float
### get_available() -> float
### get_position_profit() -> float
### get_close_profit() -> float
### get_margin() -> float
### get_commission() -> float

快捷账户字段访问。

### query_account()

主动查询 CTP 账户（仅实盘）。查询后需等待 0.3-0.5 秒再读取。

### query_position(symbol="")

主动查询 CTP 持仓。

### query_trades(symbol="")

主动查询当日成交。

## 多数据源方法

### get_data_source(index=0)

获取数据源对象。

### get_data_sources_count() -> int

数据源数量。

### require_data_sources(count) -> bool

确认至少有 count 个数据源可用。多品种策略入口应调用此方法。

## 运行时状态方法

### get_runtime_stats() -> Dict[str, Any]

运行时快照：队列积压、计时、压力等级等。

### get_runtime_pressure() -> str

压力等级: `'normal'` | `'busy'` | `'critical'`。

### is_runtime_under_pressure(level='busy') -> bool

当前压力是否 >= 指定等级。

## 自动移仓方法

### is_rollover_busy(index=0) -> bool

指定数据源是否正在执行移仓（`sent_for` 非空）。

### get_rollover_status() -> Dict[str, Any]

移仓引擎完整状态快照。

## 工具方法

### log(message: str)

输出日志消息。

### get_params() -> Dict

获取完整策略参数字典。

### get_param(key, default=None)

获取单个参数。

## 已废弃方法

| 废弃方法 | 替代 |
|---------|------|
| `get_current_datetime` | `get_datetime` |
| `get_current_price` | `get_price` |
| `get_current_pos` | `get_pos` |
| `get_current_idx` | `get_idx` |
