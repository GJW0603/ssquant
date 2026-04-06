---
name: ssquant-data
description: 查询和处理 SSQuant 框架中的行情、持仓、账户和订单流数据
version: 0.4.4
tags: [quant, futures, data, kline, tick, order-flow]
author: SSQuant Team
---

# SSQuant 数据查询技能

## 你是什么

你是一个专业的期货数据查询助手，能够帮助用户在 SSQuant 框架中获取和分析行情数据、持仓信息、账户资金和订单流数据。

**框架 v0.4.4**：发布说明见 **`更新日志_v0.4.4.md`**；data_server 历史 K 线与鉴权共用 `api_url` + `fallback_servers` 顺序。

## 数据获取方式

### 策略内查询（通过 StrategyAPI）

```python
def strategy(api: StrategyAPI):
    # K线数据
    klines = api.get_klines()              # 默认窗口
    klines = api.get_klines(window=100)    # 最近100条
    klines = api.get_klines(window=0)      # 全部

    # 当前价格
    price = api.get_price()                # 复权价
    raw = api.get_raw_price()              # 原始价

    # OHLCV 序列
    close = api.get_close()
    open_ = api.get_open()
    high = api.get_high()
    low = api.get_low()
    volume = api.get_volume()

    # 时间和索引
    dt = api.get_datetime()
    idx = api.get_idx()
```

### K 线 DataFrame 结构

标准列:

| 列名 | 类型 | 说明 |
|------|------|------|
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | int/float | 成交量 |

data_server 模式下可能的额外列:

| 列名 | 说明 |
|------|------|
| `开仓` | 开仓量 |
| `平仓` | 平仓量 |
| `多开` | 多头开仓 |
| `空开` | 空头开仓 |
| `多平` | 多头平仓 |
| `空平` | 空头平仓 |
| `B` | 主买量 |
| `S` | 主卖量 |

## Tick 数据

```python
def strategy(api: StrategyAPI):
    # 当前 Tick
    tick = api.get_tick()
    if tick is not None:
        last = tick["last_price"]
        bid1 = tick["bid_price1"]
        ask1 = tick["ask_price1"]
        bid_vol = tick["bid_volume1"]
        ask_vol = tick["ask_volume1"]
        oi = tick["open_interest"]

    # 最近 N 条 Tick
    ticks = api.get_ticks(window=50)

    # Tick 缓存数量
    count = api.get_ticks_count()
```

### Tick 配置要求

```python
config = get_config(
    ...,
    enable_tick_callback=True,
    tick_callback_interval=0.5,    # 回调间隔（秒）
    tick_queue_maxsize=20000,
)
```

## 持仓查询

```python
def strategy(api: StrategyAPI):
    # 净持仓
    net = api.get_pos()            # 多-空

    # 方向持仓
    long = api.get_long_pos()
    short = api.get_short_pos()

    # 详细持仓
    detail = api.get_position_detail()
    # {
    #   "net_pos": 1,
    #   "long_pos": 1, "short_pos": 0,
    #   "long_today": 0, "long_yd": 1,
    #   "short_today": 0, "short_yd": 0,
    # }
```

### 多数据源持仓

```python
def strategy(api: StrategyAPI):
    if api.require_data_sources(2):
        rb_pos = api.get_pos(index=0)
        hc_pos = api.get_pos(index=1)
```

## 账户资金

```python
def strategy(api: StrategyAPI):
    account = api.get_account()
    # {
    #   "balance": 100000.0,
    #   "available": 80000.0,
    #   "position_profit": 500.0,
    #   "close_profit": 200.0,
    #   "commission": 50.0,
    #   "frozen_margin": 0.0,
    #   "curr_margin": 10000.0,
    #   "update_time": "14:30:00",
    # }

    # 快捷方法
    balance = api.get_balance()
    available = api.get_available()
    margin = api.get_margin()
    profit = api.get_position_profit()

    # 主动查询（实盘，有频率限制）
    api.query_account()
    # 等待 0.3-0.5 秒后再读取
```

## 连续合约与复权

### 合约代码规则

| 后缀 | 含义 | 示例 |
|------|------|------|
| `888` | 主力连续 | `rb888` |
| `777` | 次主力连续 | `rb777` |
| `000` | 指数合约 | `rb000` |
| 具体月份 | 实际合约 | `rb2510` |

### 复权处理

```python
config = get_config(
    ...,
    adjust_type="1",    # '0'不复权 / '1'后复权 / '2'前复权
)

def strategy(api):
    price = api.get_price()        # 复权后价格
    raw = api.get_raw_price()      # 原始价格（仅 data_server 模式有效）
```

**后复权 (`'1'`)**: 调整历史价格，当前价格不变。适合回测收益计算。
**前复权 (`'2'`)**: 调整当前价格，历史价格不变。适合与实际报价对比。

### 本地复权算法

`ssquant/data/local_adjust.py` 在合约切换点计算复权因子：
- 因子 = 前合约收盘价 / 新合约开盘价
- 后复权: 历史价格 × 累计因子
- 前复权: 全部价格归一化到当前合约

## data_server 模式

服务器推送任意周期 K 线和订单流，无需本地聚合。

```python
config = get_config(
    ...,
    kline_source="data_server",
    kline_period="1m",             # 服务器直推该周期
)

def strategy(api):
    klines = api.get_klines()

    # 订单流列（仅 data_server 模式）
    if "B" in klines.columns:
        buy_vol = klines["B"].iloc[-1]    # 主买
        sell_vol = klines["S"].iloc[-1]   # 主卖
```

### HTTP 鉴权与历史 K 线（v0.4.4）

回测/预加载从 data_server 拉取历史 K 线时，使用的 HTTP 基址与鉴权一致：**顶层 `api_url` + `fallback_servers[*].api_url`** 依次尝试。若只把地址写在 `fallback_servers`、未配顶层 `api_url`，行为与旧版不同（旧版可能「鉴权成功但拉不到线」）。配置见 `ssquant/config/_server_config.py`（或与账户内 `data_server` 合并后的字典）。

## 数据持久化

### 配置保存

```python
config = get_config(
    ...,
    save_kline_csv=True,
    save_kline_db=True,
    save_tick_csv=True,
    save_tick_db=True,
    data_save_path="live_data",
    db_path="",
)
```

### 数据管理工具

参考 `examples/A_工具_数据库管理_查看与删除.py` 和 `examples/A_工具_导入数据库DB示例.py`。

## 运行时监控数据

```python
def strategy(api: StrategyAPI):
    # 运行时统计
    stats = api.get_runtime_stats()
    # 包含: 队列积压、计时、压力等级等

    # 压力等级
    pressure = api.get_runtime_pressure()
    # 'normal' / 'busy' / 'critical'

    # 压力判断
    if api.is_runtime_under_pressure("busy"):
        api.log("系统忙碌，减少计算量")

    # 移仓状态
    roll = api.get_rollover_status()
    busy = api.is_rollover_busy()
```

## 常用指标计算模式

```python
def strategy(api: StrategyAPI):
    klines = api.get_klines()
    close = api.get_close()

    # 均线
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()

    # 布林带
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = mid + 2 * std
    lower = mid - 2 * std

    # ATR
    high = api.get_high()
    low = api.get_low()
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss)
```
