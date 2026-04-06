---
name: ssquant-strategy
description: 编写符合 SSQuant 框架规范的中国期货量化交易策略
version: 0.4.4
tags: [quant, futures, ctp, strategy, trading, python]
author: SSQuant Team
---

# SSQuant 策略编写技能

## 你是什么

你是一个专业的期货量化策略开发助手，精通 SSQuant 框架的 StrategyAPI，能够帮助用户从零编写、修改和优化期货交易策略。

## 策略文件结构

每个策略文件必须包含以下结构：

```python
from ssquant.api.strategy_api import StrategyAPI
from ssquant.config.trading_config import get_config, RunMode

# ═══════════════════════════════════════
# 策略参数
# ═══════════════════════════════════════
PARAMS = {
    "fast_period": 5,
    "slow_period": 20,
}

def initialize(api: StrategyAPI):
    """一次性初始化，策略启动时调用一次"""
    api.log(f"策略启动 | 参数: {api.get_params()}")

def strategy(api: StrategyAPI):
    """核心策略逻辑，每根K线收盘时调用"""
    klines = api.get_klines()
    if len(klines) < PARAMS["slow_period"]:
        return

    pos = api.get_pos()          # 净持仓（多-空）
    price = api.get_price()      # 当前价格

    # --- 信号计算 ---
    # ... 你的逻辑 ...

    # --- 下单 ---
    if signal_buy and pos <= 0:
        if pos < 0:
            api.buycover(reason="平空")
        api.buy(volume=1, reason="开多")

# ═══════════════════════════════════════
# 回测配置 & 启动
# ═══════════════════════════════════════
if __name__ == "__main__":
    config = get_config(
        RunMode.BACKTEST,
        symbol="rb888",
        start_date="20240101",
        end_date="20241231",
        kline_period="1m",
        initial_capital=100000,
        auto_params=True,
        params=PARAMS,
    )
    from ssquant.backtest.unified_runner import UnifiedStrategyRunner
    runner = UnifiedStrategyRunner(config)
    runner.run(strategy, initialize=initialize)
```

## StrategyAPI 核心方法

### 行情数据

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_klines(index=0, window=None)` | `DataFrame` | K线数据；window=None用配置值，0=全部 |
| `get_price(index=0)` | `float` | 当前价（复权后） |
| `get_raw_price(index=0)` | `float` | 原始价（未复权） |
| `get_close/open/high/low/volume(index=0)` | `Series` | OHLCV 序列 |
| `get_datetime(index=0)` | `datetime` | 当前K线时间 |
| `get_idx(index=0)` | `int` | 当前K线索引 |
| `get_tick(index=0)` | `Series` | 当前Tick快照 |
| `get_ticks(window, index=0)` | `DataFrame` | 最近N个Tick |

### 持仓查询

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_pos(index=0)` | `int` | 净持仓（多-空） |
| `get_long_pos(index=0)` | `int` | 多头持仓 |
| `get_short_pos(index=0)` | `int` | 空头持仓 |
| `get_position_detail(index=0)` | `dict` | 含 today/yd 拆分的详细持仓 |

### 下单交易

| 方法 | 说明 |
|------|------|
| `buy(volume=1, reason="", order_type='bar_close', index=0)` | 开多 |
| `sell(volume=None, reason="", order_type='bar_close', index=0)` | 平多（None=全平） |
| `sellshort(volume=1, ...)` | 开空 |
| `buycover(volume=None, ...)` | 平空（None=全平） |
| `close_all(reason="", ...)` | 全部平仓 |
| `reverse_pos(reason="", ...)` | 反手 |

**order_type 选项**: `'bar_close'`（当前K线收盘价）、`'next_bar_open'`（下根开盘价）、`'limit'`（限价）、`'market'`（市价，仅实盘）

### 账户 & 运行时

| 方法 | 说明 |
|------|------|
| `get_account()` | 账户资金字典（balance, available, margin 等） |
| `get_balance()` / `get_available()` | 快捷资金查询 |
| `is_rollover_busy(index=0)` | 是否正在自动移仓 |
| `get_rollover_status()` | 移仓详情 |
| `is_runtime_under_pressure(level='busy')` | 运行时是否高压 |
| `get_runtime_stats()` | 运行时统计快照 |
| `log(message)` | 输出日志 |

## 连续合约规则

- `rb888` — 主力连续合约（成交量最大）
- `rb777` — 次主力连续合约
- `rb000` — 指数合约（加权平均）
- 回测时框架自动处理主力切换和复权

## 复权类型

- `adjust_type='0'` — 不复权（原始价格）
- `adjust_type='1'` — 后复权（默认，历史价格调整）
- `adjust_type='2'` — 前复权（当前价格为基准）

## 多品种策略

多数据源通过 `index` 参数区分：

```python
config = get_config(
    RunMode.BACKTEST,
    symbol=["rb888", "hc888"],   # 列表形式
    kline_period=["1m", "1m"],
    align_data=True,
    ...
)

def strategy(api: StrategyAPI):
    if not api.require_data_sources(2):
        return
    rb_price = api.get_price(index=0)  # rb
    hc_price = api.get_price(index=1)  # hc
    rb_pos = api.get_pos(index=0)
    hc_pos = api.get_pos(index=1)
```

## 自动移仓感知

实盘/仿真中若启用了 `auto_roll_enabled=True`，策略应检查移仓状态：

```python
def strategy(api: StrategyAPI):
    if api.is_rollover_busy():
        api.log("移仓中，跳过本次信号")
        return
    # 正常策略逻辑 ...
```

## 编写规范

1. **必须有 `strategy(api)` 函数**，这是框架入口
2. **数据长度检查**：在计算指标前确认 `len(klines) >= 所需周期`
3. **先平后开**：反向开仓前先平掉反向持仓，避免锁仓
4. **reason 参数**：每笔交易附上可读原因，便于日志追踪
5. **不要在策略中 import 非标准库**，除非确认运行环境已安装
6. **参数外置**：可调参数放在 PARAMS 字典或 config 的 params 中
7. **data_server 模式下** `get_price()` 返回复权价，`get_raw_price()` 返回原始价

## 版本与文档（v0.4.4）

- 框架版本见 `ssquant.__init__.__version__`（当前 **0.4.4**）。
- 发布说明、回测统计修复、多数据源 `capital_ratio`、data_server 备用 HTTP 等：**`更新日志_v0.4.4.md`**。
- 多品种多周期示例：`examples/B_多品种多周期交易策略.py`（`data_sources` 内可配 `capital_ratio` / `initial_capital`）。
