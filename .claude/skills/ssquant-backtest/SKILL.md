---
name: ssquant-backtest
description: 配置并执行 SSQuant 期货策略回测，分析回测结果
version: 0.4.3
tags: [quant, futures, backtest, optimization, python]
author: SSQuant Team
---

# SSQuant 回测验证技能

## 你是什么

你是一个专业的期货策略回测助手，能够帮助用户配置回测参数、执行回测、解读回测结果，以及进行参数优化。

## 回测执行流程

```python
from ssquant.config.trading_config import get_config, RunMode
from ssquant.backtest.unified_runner import UnifiedStrategyRunner

config = get_config(
    RunMode.BACKTEST,
    symbol="rb888",
    start_date="20240101",
    end_date="20241231",
    kline_period="1m",
    initial_capital=100000,
    auto_params=True,      # 自动填充合约乘数、手续费等
    params={"fast": 5, "slow": 20},
)

runner = UnifiedStrategyRunner(config)
runner.run(strategy, initialize=initialize)
```

## get_config 关键参数

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `mode` | `RunMode` | `RunMode.BACKTEST` |
| `symbol` | `str / list` | 合约代码，如 `"rb888"` 或 `["rb888", "hc888"]` |
| `start_date` | `str` | 起始日期 `"YYYYMMDD"` |
| `end_date` | `str` | 结束日期 `"YYYYMMDD"` |

### 常用可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `kline_period` | `"1m"` | K线周期: `1m/3m/5m/15m/30m/1h/1d` |
| `initial_capital` | `20000` | 初始资金（元） |
| `commission` | `0.0001` | 手续费率 |
| `margin_rate` | `0.1` | 保证金率 |
| `contract_multiplier` | `10` | 合约乘数 |
| `price_tick` | `1.0` | 最小变动价位 |
| `slippage_ticks` | `1` | 滑点（tick 数） |
| `adjust_type` | `'1'` | 复权: `'0'`不复权 / `'1'`后复权 / `'2'`前复权 |
| `auto_params` | `True` | 自动从服务器获取合约参数 |
| `lookback_bars` | `0` | K线回溯长度（0=不限） |
| `align_data` | `False` | 多品种时间对齐 |
| `fill_method` | `'ffill'` | 对齐填充方式 |
| `use_cache` | `True` | 使用本地缓存 |
| `debug` | `False` | 调试模式 |
| `params` | `{}` | 策略自定义参数字典 |

### 时间精确控制

| 参数 | 说明 |
|------|------|
| `start_time` | 每日开始时间 `"HH:MM"` |
| `end_time` | 每日结束时间 `"HH:MM"` |
| `limit` | 限制返回的 K 线条数 |

### 资金约束（v0.4.3）

回测引擎会检查开仓资金：
- 资金不足时自动削减手数或拒绝开仓
- 被拒绝的订单会在日志中显示 `[REJECT]`
- 启用 `debug=True` 可看到详细资金流水

## auto_params 自动参数

当 `auto_params=True` 时，框架从服务器查询合约信息自动填充：

- `contract_multiplier` — 合约乘数
- `price_tick` — 最小变动价位
- `margin_rate` — 保证金率
- `commission` — 手续费率（按手或按金额）

用户显式设置的值不会被覆盖。

## 参数优化

```python
import itertools

fast_range = [3, 5, 8, 10]
slow_range = [15, 20, 30, 50]
results = []

for fast, slow in itertools.product(fast_range, slow_range):
    if fast >= slow:
        continue
    config = get_config(
        RunMode.BACKTEST,
        symbol="rb888",
        start_date="20240101",
        end_date="20241231",
        kline_period="1m",
        initial_capital=100000,
        auto_params=True,
        params={"fast": fast, "slow": slow},
    )
    runner = UnifiedStrategyRunner(config)
    result = runner.run(strategy, initialize=initialize)
    results.append({"fast": fast, "slow": slow, **result})
```

## 自动移仓回测

```python
config = get_config(
    RunMode.BACKTEST,
    symbol="rb888",
    start_date="20240101",
    end_date="20241231",
    kline_period="1m",
    auto_roll_enabled=True,
    auto_roll_mode="simultaneous",    # simultaneous / sequential
    auto_roll_reopen=True,            # 移仓后自动重新开仓
    auto_roll_log_enabled=True,       # 记录移仓日志
)
```

## 回测结果解读

回测完成后输出的关键指标：

| 指标 | 含义 | 健康范围 |
|------|------|---------|
| 总收益率 | 净盈亏 / 初始资金 | 正值 |
| 年化收益率 | 按交易天数折算 | > 无风险利率 |
| 最大回撤 | 峰值到谷值最大跌幅 | < 30% |
| 夏普比率 | 超额收益 / 收益波动率 | > 1.0 |
| 胜率 | 盈利交易 / 总交易次数 | > 40%（趋势策略） |
| 盈亏比 | 平均盈利 / 平均亏损 | > 1.5 |

## 常见问题

**Q: 回测结果全是 0？**
- 检查 `start_date/end_date` 范围内是否有数据
- 检查 `symbol` 是否正确（`rb888` 不是 `RB888`）
- 检查策略逻辑是否真的发出了交易信号

**Q: 回测速度很慢？**
- 减小日期范围先验证逻辑
- 使用 `use_cache=True` 缓存数据
- 减少 `lookback_bars` 缩小 DataFrame

**Q: 资金不足导致无法开仓？**
- 增加 `initial_capital`
- 减少 `volume`
- 检查 `margin_rate` 和 `contract_multiplier` 是否合理
