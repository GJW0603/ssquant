# SSQuant 策略示例参考

## 1. 双均线策略（入门经典）

```python
from ssquant.api.strategy_api import StrategyAPI
from ssquant.config.trading_config import get_config, RunMode

PARAMS = {"fast": 5, "slow": 20}

def initialize(api: StrategyAPI):
    api.log(f"双均线策略启动 | fast={api.get_param('fast')} slow={api.get_param('slow')}")

def strategy(api: StrategyAPI):
    klines = api.get_klines()
    slow = api.get_param("slow")
    if len(klines) < slow:
        return

    close = api.get_close()
    ma_fast = close.rolling(api.get_param("fast")).mean()
    ma_slow = close.rolling(slow).mean()

    pos = api.get_pos()
    if ma_fast.iloc[-1] > ma_slow.iloc[-1] and ma_fast.iloc[-2] <= ma_slow.iloc[-2]:
        if pos < 0:
            api.buycover(reason="金叉平空")
        if pos <= 0:
            api.buy(volume=1, reason="金叉开多")
    elif ma_fast.iloc[-1] < ma_slow.iloc[-1] and ma_fast.iloc[-2] >= ma_slow.iloc[-2]:
        if pos > 0:
            api.sell(reason="死叉平多")
        if pos >= 0:
            api.sellshort(volume=1, reason="死叉开空")

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

## 2. 多品种对冲策略

```python
PARAMS = {"spread_threshold": 50}

def strategy(api: StrategyAPI):
    if not api.require_data_sources(2):
        return

    klines_a = api.get_klines(index=0)
    klines_b = api.get_klines(index=1)
    if len(klines_a) < 5 or len(klines_b) < 5:
        return

    price_a = api.get_price(index=0)
    price_b = api.get_price(index=1)
    spread = price_a - price_b
    threshold = api.get_param("spread_threshold")

    pos_a = api.get_pos(index=0)
    if spread > threshold and pos_a <= 0:
        api.buycover(index=1, reason="价差回归-平空B")
        api.sell(index=0, reason="价差回归-平多A")
        api.sellshort(volume=1, index=0, reason="做空A")
        api.buy(volume=1, index=1, reason="做多B")
    elif spread < -threshold and pos_a >= 0:
        api.sell(index=1, reason="价差回归-平多B")
        api.buycover(index=0, reason="价差回归-平空A")
        api.buy(volume=1, index=0, reason="做多A")
        api.sellshort(volume=1, index=1, reason="做空B")

if __name__ == "__main__":
    config = get_config(
        RunMode.BACKTEST,
        symbol=["rb888", "hc888"],
        kline_period=["1m", "1m"],
        start_date="20240101",
        end_date="20241231",
        align_data=True,
        initial_capital=200000,
        auto_params=True,
        params=PARAMS,
    )
    from ssquant.backtest.unified_runner import UnifiedStrategyRunner
    runner = UnifiedStrategyRunner(config)
    runner.run(strategy)
```

## 3. 带移仓感知的实盘策略模板

```python
def strategy(api: StrategyAPI):
    if api.is_rollover_busy():
        api.log("⏳ 移仓进行中，跳过信号")
        return

    if api.is_runtime_under_pressure("critical"):
        api.log("⚠️ 系统高压，仅平仓操作")
        if api.get_pos() != 0:
            api.close_all(reason="高压保护平仓")
        return

    klines = api.get_klines()
    if len(klines) < 20:
        return

    # 正常策略逻辑 ...
```

## 4. Tick 驱动策略要点

```python
def strategy(api: StrategyAPI):
    tick = api.get_tick()
    if tick is None:
        return

    bid = tick.get("bid_price1", 0)
    ask = tick.get("ask_price1", 0)
    spread = ask - bid

    # Tick 级别的快速判断
    if spread <= price_tick:
        # 极窄价差时的交易逻辑
        pass
```

配置要点：
- `enable_tick_callback=True`
- `tick_callback_interval=0.5`（防开盘洪峰）
- `tick_queue_maxsize=20000`

## 5. data_server 模式 + 订单流

```python
def strategy(api: StrategyAPI):
    klines = api.get_klines()
    if len(klines) < 10:
        return

    # data_server 模式下 K 线可能包含订单流列
    if "多开" in klines.columns:
        buy_open = klines["多开"].iloc[-1]
        sell_open = klines["空开"].iloc[-1]
        net_flow = buy_open - sell_open
        api.log(f"订单流净值: {net_flow}")
```

配置要点：
- `kline_source='data_server'`
- data_server 模式下服务器推送任意周期 K 线，无需本地聚合

## 示例文件速查

| 文件 | 类型 | 特点 |
|------|------|------|
| `B_双均线策略.py` | 回测 | 入门模板，完整注释 |
| `B_自动换月示例.py` | 回测 | 移仓感知 + auto_roll 配置 |
| `B_自动参数示例.py` | 回测 | 参数优化遍历 |
| `B_十大经典策略之Aberration.py` | 回测 | 布林通道策略 |
| `B_日内交易策略.py` | 回测 | 日内平仓逻辑 |
| `B_海龟交易策略.py` | 回测 | 经典趋势跟踪 |
| `B_网格交易策略.py` | 回测 | 网格交易 |
| `B_机器学习策略_随机森林.py` | 回测 | ML + 量化 |
| `B_多品种多周期交易策略.py` | 回测 | 多数据源 + 跨周期 |
| `B_跨期套利策略.py` | 回测 | 同品种不同月份套利 |
| `B_跨品种套利策略.py` | 回测 | 不同品种间套利 |
| `B_强弱截面轮动策略.py` | 回测 | 多品种动量轮动 |
| `B_跨周期过滤策略.py` | 回测 | 大周期过滤 + 小周期执行 |
| `C_纯Tick限价单交易策略.py` | 高级 | Tick 驱动限价单 |
| `C_纯Tick高频交易策略.py` | 高级 | 高频逻辑 |
| `C_期权交易策略.py` | 高级 | 期权交易 |
| `D_订单流与深度数据_data_server模式.py` | 数据 | 订单流分析 |
| `A_CTP连接状态监测测试_真实断网.py` | 工具 | 网络断线检测 |
| `A_撤单重发示例.py` | 工具 | 算法交易撤单重发 |
| `A_穿透式测试脚本.py` | 工具 | CTP 穿透式认证 |
| `A_工具_数据库管理_查看与删除.py` | 工具 | 本地数据库管理 |
| `A_工具_导入数据库DB示例.py` | 工具 | 数据导入 |
