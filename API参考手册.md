# API参考手册

> SSQuant v0.4.3 完整API参考

## 📖 目录

1. [数据查询API](#数据查询api)
2. [持仓查询API](#持仓查询api)
3. [交易操作API](#交易操作api)
4. [账户资金API](#账户资金api)
5. [TICK数据API](#tick数据api)
6. [多数据源API](#多数据源api)
7. [参数和日志API](#参数和日志api)
8. [运行时状态API](#运行时状态api)
9. [自动移仓API](#自动移仓api)
10. [实盘专用API](#实盘专用api)
11. [回调函数](#回调函数)
12. [配置参数参考](#配置参数参考)

---

## 数据查询API

### api.get_close(index=0)

获取收盘价序列。

**参数：**
- `index` (int): 数据源索引，默认0

**返回：**
- `pd.Series`: 收盘价序列

**示例：**

```python
close = api.get_close()
ma20 = close.rolling(20).mean()
current_price = close.iloc[-1]
```

---

### api.get_open(index=0)

获取开盘价序列。

---

### api.get_high(index=0)

获取最高价序列。

---

### api.get_low(index=0)

获取最低价序列。

---

### api.get_volume(index=0)

获取成交量序列。

---

### api.get_klines(index=0, window=None)

获取完整的K线数据。

**参数：**
- `index` (int): 数据源索引
- `window` (int/None): 滑动窗口大小。`None` = 使用配置的 `lookback_bars`，`0` = 不限制（全部历史）

**返回：**
- `pd.DataFrame`: 包含 `datetime`, `open`, `high`, `low`, `close`, `volume` 等列。data_server 模式下还包含订单流字段。

**示例：**

```python
klines = api.get_klines()
latest = klines.iloc[-1]

# 指定获取最近100条
klines = api.get_klines(0, window=100)

# 获取全部数据
klines = api.get_klines(0, window=0)
```

---

### api.get_price(index=0)

获取当前价格。在复权模式下返回复权后价格，与 `get_close()` 口径一致。

**返回：**
- `float/None`: 当前价格

---

### api.get_raw_price(index=0)

获取原始未复权价格，更接近底层行情/委托定价口径。

**返回：**
- `float/None`: 未复权价格

> 💡 下单时框架内部使用原始价格，策略分析建议使用 `get_price()`。

---

### api.get_datetime(index=0)

获取当前K线时间。

**返回：**
- `pd.Timestamp`: 当前K线的时间

---

### api.get_idx(index=0)

获取当前K线索引（从0开始）。

**返回：**
- `int`: 当前索引

```python
if api.get_idx() < 20:
    return  # 数据不足，跳过
```

---

## 持仓查询API

### api.get_pos(index=0)

获取净持仓。

**返回：**
- `int`: 正数=多头，负数=空头，0=无持仓

```python
pos = api.get_pos()
if pos > 0:
    print(f"持有{pos}手多仓")
elif pos < 0:
    print(f"持有{-pos}手空仓")
```

---

### api.get_long_pos(index=0)

获取多头持仓数量（非负数）。

---

### api.get_short_pos(index=0)

获取空头持仓数量（非负数）。

---

### api.get_position_detail(index=0)

获取详细持仓信息。

**返回字段：**

| 字段 | 说明 |
|------|------|
| `net_pos` | 净持仓 |
| `long_pos` | 多头持仓 |
| `short_pos` | 空头持仓 |
| `today_pos` | 今仓（净） |
| `yd_pos` | 昨仓（净） |
| `long_today` | 多头今仓 |
| `short_today` | 空头今仓 |
| `long_yd` | 多头昨仓 |
| `short_yd` | 空头昨仓 |

```python
detail = api.get_position_detail()
print(f"多头: {detail['long_pos']} (今:{detail['long_today']} 昨:{detail['long_yd']})")
```

---

## 交易操作API

### api.buy()

买入开仓（做多）。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `volume` | int | 1 | 手数 |
| `reason` | str | "" | 交易原因 |
| `order_type` | str | `'bar_close'` | 订单类型 |
| `index` | int | 0 | 数据源索引 |
| `offset_ticks` | int/None | None | 价格偏移（覆盖配置） |
| `price` | float/None | None | 限价单价格 |

**order_type 选项：**

| 值 | 回测成交价 | 实盘委托 |
|----|----------|---------|
| `'bar_close'` | 当前K线收盘价 | 当前价 |
| `'next_bar_open'` | 下一K线开盘价 | 等下一根K线 |
| `'next_bar_close'` | 下一K线收盘价 | 等下一根K线 |
| `'next_bar_high'` | 下一K线最高价 | 条件单 |
| `'next_bar_low'` | 下一K线最低价 | 条件单 |
| `'market'` | 对价成交 | 市价/超价委托 |
| `'limit'` | (不支持) | 限价单 |

**示例：**

```python
api.buy(volume=1, order_type='next_bar_open')
api.buy(volume=1, reason='金叉信号', order_type='next_bar_open')
api.buy(volume=1, order_type='market', offset_ticks=10)
api.buy(volume=1, price=3500.0)  # 限价单
api.buy(volume=1, order_type='limit', price=3500.0)
```

> v0.4.3: 回测模式下资金不足时会自动裁剪手数或拒单。

---

### api.sell()

卖出平仓（平多）。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `volume` | int/None | None | 手数，None=平所有多仓 |
| `reason` | str | "" | 交易原因 |
| `order_type` | str | `'bar_close'` | 订单类型 |
| `index` | int | 0 | 数据源索引 |
| `offset_ticks` | int/None | None | 价格偏移 |
| `price` | float/None | None | 限价单价格 |

```python
api.sell(order_type='next_bar_open')       # 平所有多仓
api.sell(volume=2, order_type='next_bar_open')  # 平指定手数
api.sell(volume=1, price=3600.0)           # 限价平仓
```

---

### api.sellshort()

卖出开仓（做空）。参数同 `api.buy()`。

```python
api.sellshort(volume=1, order_type='next_bar_open')
```

---

### api.buycover()

买入平仓（平空）。参数同 `api.sell()`。

```python
api.buycover(order_type='next_bar_open')
```

---

### api.buytocover()

同 `api.buycover()`，别名。

---

### api.close_all(reason="", order_type='bar_close', index=0)

平掉所有持仓（多头和空头）。

```python
api.close_all(order_type='next_bar_open', reason='收盘平仓')
```

---

### api.reverse_pos(reason="", order_type='bar_close', index=0)

反手（多转空，空转多）。

```python
api.reverse_pos(order_type='next_bar_open')
```

---

## 账户资金API

> 以下API仅在 SIMNOW/实盘 模式下有效，回测模式返回0。

### api.get_account()

获取完整账户信息。

**返回字段：**

| 字段 | 说明 |
|------|------|
| `balance` | 账户权益 |
| `available` | 可用资金 |
| `position_profit` | 持仓盈亏 |
| `close_profit` | 平仓盈亏 |
| `commission` | 手续费 |
| `frozen_margin` | 冻结保证金 |
| `curr_margin` | 占用保证金 |
| `update_time` | 更新时间 |

```python
account = api.get_account()
print(f"权益: {account['balance']}, 可用: {account['available']}")
```

---

### api.get_balance()

获取账户权益。

---

### api.get_available()

获取可用资金。

---

### api.get_position_profit()

获取持仓浮动盈亏。

---

### api.get_close_profit()

获取当日平仓盈亏。

---

### api.get_margin()

获取当前占用保证金。

---

### api.get_commission()

获取当日手续费。

---

### api.query_account()

主动触发CTP账户查询。查询后等待 0.3-0.5 秒再读取。

```python
api.query_account()
import time
time.sleep(0.5)
account = api.get_account()
```

> CTP 有查询频率限制，建议不要频繁调用。

---

### api.query_position(symbol="")

主动查询持仓。空字符串=查询所有持仓。

---

### api.query_trades(symbol="")

主动查询当日成交记录。

---

## TICK数据API

> TICK数据仅在 SIMNOW/实盘 模式下可用，回测模式返回None

### api.get_tick(index=0)

获取当前TICK数据。

**常用字段：**

| 字段 | 说明 |
|------|------|
| `LastPrice` | 最新价 |
| `OpenPrice` | 开盘价 |
| `HighestPrice` | 最高价 |
| `LowestPrice` | 最低价 |
| `AskPrice1` | 卖一价 |
| `BidPrice1` | 买一价 |
| `AskVolume1` | 卖一量 |
| `BidVolume1` | 买一量 |
| `Volume` | 累计成交量 |
| `OpenInterest` | 持仓量 |
| `TradingDay` | 交易日 |
| `UpdateTime` | 时间(HH:MM:SS) |
| `UpdateMillisec` | 毫秒 |

```python
tick = api.get_tick()
if tick:
    print(f"最新价: {tick.get('LastPrice', 0):.2f}")
    print(f"卖一: {tick.get('AskPrice1', 0):.2f}")
    print(f"买一: {tick.get('BidPrice1', 0):.2f}")
```

---

### api.get_ticks(window=None, index=0)

获取最近N个TICK数据。

**参数：**
- `window` (int/None): 窗口大小，None=使用 `lookback_bars`，`0`=全部缓存

```python
ticks = api.get_ticks(window=50)
print(f"最近50个TICK的平均价: {ticks['LastPrice'].mean():.2f}")
```

---

### api.get_ticks_count(index=0)

获取当前缓存的TICK数据总数。

```python
tick_count = api.get_ticks_count()
all_ticks = api.get_ticks(window=tick_count)
```

---

## 多数据源API

### api.get_data_sources_count()

获取数据源数量。

---

### api.get_data_source(index)

获取指定数据源对象。

```python
ds = api.get_data_source(0)
print(ds.symbol)
print(ds.kline_period)
```

---

### api.require_data_sources(count)

确保至少有指定数量的数据源。

```python
def multi_strategy(api):
    if not api.require_data_sources(2):
        return
```

---

### 访问不同数据源

所有数据和交易API都支持 `index` 参数：

```python
config = get_config(
    mode=RunMode.BACKTEST,
    data_sources=[
        {'symbol': 'rb888', 'kline_period': '1h'},
        {'symbol': 'i888', 'kline_period': '1h'},
    ],
)

def multi_strategy(api):
    close_rb = api.get_close(index=0)
    close_i = api.get_close(index=1)
    api.buy(volume=1, index=0)
    api.buy(volume=1, index=1)
```

---

## 参数和日志API

### api.get_param(key, default=None)

获取策略参数。

```python
runner.run(
    strategy=my_strategy,
    strategy_params={'ma_period': 20, 'stop_loss': 0.05}
)

# 策略中获取
ma_period = api.get_param('ma_period', 20)
```

---

### api.get_params()

获取所有参数字典。

---

### api.log(message)

记录日志。

```python
api.log(f"当前价格: {price:.2f}, 持仓: {pos}")
```

---

## 运行时状态API

> v0.4.3 新增。仅在 SIMNOW/实盘 模式下有效。

### api.get_runtime_stats()

获取运行时状态快照，包含队列积压、处理耗时、压力等级等。

**返回：**
- `dict`: 统计信息

| 字段 | 说明 |
|------|------|
| `pressure_level` | 压力等级：`normal` / `busy` / `critical` |
| `queue_size` | 当前队列长度 |
| `high_water_mark` | 高水位值 |
| `overflow_count` | 溢出缓冲累计次数 |
| `compress_count` | 积压压缩次数 |

---

### api.get_runtime_pressure()

获取运行时压力等级。

**返回：**
- `str`: `'normal'` / `'busy'` / `'critical'`

```python
pressure = api.get_runtime_pressure()
if pressure == 'critical':
    api.log("系统高压，暂停交易")
    return
```

---

### api.is_runtime_under_pressure(level='busy')

判断是否达到指定压力等级及以上。

```python
if api.is_runtime_under_pressure('busy'):
    return  # 跳过本次
```

---

## 自动移仓API

> v0.4.3 新增。仅在启用自动移仓的 SIMNOW/实盘 模式下有效。

### api.is_rollover_busy(index=0)

当前数据源是否处于移仓等待闭环。

**返回：**
- `bool`: `True` = 正在移仓（已发移仓单、尚未确认完成）

```python
if api.is_rollover_busy():
    return  # 移仓中，暂停交易信号
```

---

### api.get_rollover_status()

获取移仓状态快照。

**返回结构：**

```python
{
    'per_source': {
        '0': {
            'sent_for': 'rb2505',        # 正在移仓的旧合约（None=空闲）
            'expected_vol': 1,            # 预期移仓手数
            'expected_dir': 'long',       # 方向
            'wait_invocations': 3,        # 等待次数
            'seq_phase': 'wait_close',    # sequential模式阶段
        }
    }
}
```

---

## 实盘专用API

### api.cancel_all_orders(index=0)

撤销所有未成交订单。

```python
api.cancel_all_orders()
import time
time.sleep(0.3)
api.buy(volume=1, order_type='market')
```

---

### offset_ticks 参数

下单时临时指定价格偏移，覆盖配置中的 `order_offset_ticks`。

**委托价格计算：**

```
买入委托价 = 卖一价 + offset_ticks × price_tick
卖出委托价 = 买一价 - offset_ticks × price_tick
```

```python
api.buy(volume=1, order_type='market')              # 使用配置值
api.buy(volume=1, order_type='market', offset_ticks=10)   # 超价
api.buy(volume=1, order_type='market', offset_ticks=-5)   # 折价
```

---

## 回调函数

> 回调函数仅在 SIMNOW/实盘 模式下有效

### on_trade(data)

成交回调。

| 字段 | 说明 | 类型 |
|------|------|------|
| TradeID | 成交编号 | str |
| InstrumentID | 合约代码 | str |
| Direction | 方向('0'=买,'1'=卖) | str |
| OffsetFlag | 开平('0'=开,'1'=平,'2'=强平,'3'=平今,'4'=平昨) | str |
| Price | 成交价格 | float |
| Volume | 成交数量 | int |
| TradeTime | 成交时间 | str |

```python
def on_trade(data):
    direction = '买' if data['Direction'] == '0' else '卖'
    offset_map = {'0': '开', '1': '平', '2': '强平', '3': '平今', '4': '平昨'}
    offset = offset_map.get(data['OffsetFlag'], '未知')
    print(f"成交: {data['InstrumentID']} {direction}{offset} "
          f"{data['Volume']}手 @{data['Price']:.2f}")
```

---

### on_order(data)

报单回调。

| 字段 | 说明 |
|------|------|
| OrderSysID | 订单编号 |
| InstrumentID | 合约代码 |
| Direction | 方向 |
| OrderStatus | 状态 |
| LimitPrice | 委托价格 |
| VolumeTotalOriginal | 委托数量 |
| VolumeTraded | 已成交数量 |
| StatusMsg | 状态消息 |

**OrderStatus 值：**
- `'0'`: 全部成交
- `'1'`: 部分成交
- `'2'`: 部分成交部分撤单
- `'3'`: 未成交
- `'4'`: 未成交已撤
- `'5'`: 撤单

---

### on_cancel(data)

撤单回调。

---

### on_order_error(data)

报单错误回调。

---

### on_cancel_error(data)

撤单错误回调。

---

### on_account(data)

账户资金回调。

---

### on_position(data)

持仓回调。

---

### 注册回调

```python
runner.run(
    strategy=my_strategy,
    on_trade=on_trade,
    on_order=on_order,
    on_cancel=on_cancel,
    on_order_error=on_order_error,
    on_cancel_error=on_cancel_error,
    on_account=on_account,
    on_position=on_position,
)
```

---

## 配置参数参考

### get_config() 函数

```python
config = get_config(
    mode,                      # RunMode.BACKTEST / SIMNOW / REAL_TRADING
    account=None,              # 账户名（SIMNOW/实盘必填）
    auto_params=True,          # 自动获取合约参数
    **overrides                # 覆盖参数
)
```

### 回测配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `symbol` | - | 合约代码（如 `'rb888'`） |
| `start_date` | - | 开始日期 `'YYYY-MM-DD'` |
| `end_date` | - | 结束日期 `'YYYY-MM-DD'` |
| `start_time` | - | 精确开始时间 |
| `end_time` | - | 精确结束时间 |
| `limit` | - | 最近N根K线 |
| `kline_period` | `'1h'` | K线周期 |
| `adjust_type` | `'1'` | 复权: `'0'`/`'1'`/`'2'` |
| `initial_capital` | `20000` | 初始资金 |
| `commission` | `0.0001` | 手续费率 |
| `margin_rate` | `0.1` | 保证金率 |
| `slippage_ticks` | `1` | 滑点跳数 |
| `lookback_bars` | `0` | 数据窗口（0=不限制） |
| `tick_queue_maxsize` | `20000` | Tick队列容量 |

### SIMNOW/实盘配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `kline_period` | `'1m'` | K线周期 |
| `order_offset_ticks` | `5` | 超价跳数 |
| `algo_trading` | `False` | 启用算法交易 |
| `order_timeout` | `10` | 超时时间(秒) |
| `retry_limit` | `3` | 最大重试次数 |
| `retry_offset_ticks` | `5` | 重试偏移跳数 |
| `preload_history` | `True` | 预加载历史K线 |
| `history_lookback_bars` | `100` | 预加载数量 |
| `kline_source` | `'local'` | `'local'` 或 `'data_server'` |
| `enable_tick_callback` | `False` | TICK驱动模式 |
| `tick_callback_interval` | `0.5` | 节流间隔(秒) |
| `tick_queue_maxsize` | `20000` | Tick队列容量 |
| `auto_roll_enabled` | `False` | 自动移仓 |
| `auto_roll_mode` | `'simultaneous'` | 移仓模式 |
| `auto_roll_reopen` | `True` | 是否补开新仓 |

---

## 完整示例

### 双均线策略（带止损 + 移仓感知）

```python
from ssquant.api.strategy_api import StrategyAPI

g_entry_price = 0

def my_ma_strategy(api: StrategyAPI):
    global g_entry_price
    
    # 移仓进行中不交易
    if api.is_rollover_busy():
        return
    
    close = api.get_close()
    if len(close) < 20:
        return
    
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    pos = api.get_pos()
    current_price = close.iloc[-1]
    
    # 止损
    if pos > 0 and g_entry_price > 0:
        if current_price < g_entry_price * 0.95:
            api.sell(order_type='next_bar_open', reason='止损')
            g_entry_price = 0
            return
    
    # 金叉
    if ma5.iloc[-2] <= ma20.iloc[-2] and ma5.iloc[-1] > ma20.iloc[-1]:
        if pos <= 0:
            if pos < 0:
                api.buycover(order_type='next_bar_open')
            api.buy(volume=1, order_type='next_bar_open')
            g_entry_price = current_price
    
    # 死叉
    elif ma5.iloc[-2] >= ma20.iloc[-2] and ma5.iloc[-1] < ma20.iloc[-1]:
        if pos >= 0:
            if pos > 0:
                api.sell(order_type='next_bar_open')
            api.sellshort(volume=1, order_type='next_bar_open')
            g_entry_price = current_price
```

---

查看更多示例：`examples/` 目录（共 25 个）
