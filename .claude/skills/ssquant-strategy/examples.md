# SSQuant 策略示例参考

> 与框架 **v0.4.4** 示例目录一致；发布说明见 **`更新日志_v0.4.4.md`**。

## 路径约定（便于定位文件）

- 所有示例脚本在仓库根目录的 **`examples/`** 下，完整相对路径为 **`examples/<文件名>`**（例：`examples/B_双均线策略.py`）。
- 按前缀浏览：`examples/B_*.py` 回测策略，`A_*.py` 工具，`C_*.py` 高级，`D_*.py` 数据专题。
- 下表「相对路径」列为可直接打开的文件路径。

## 文中代码片段与仓库文件

第 1～5 节为浓缩模板；与仓库中脚本对应关系：

| 片段章节 | 建议对照的示例文件 |
|----------|-------------------|
| 第 1 节 双均线 | `examples/B_双均线策略.py` |
| 第 2 节 多品种对冲 | `examples/B_跨品种套利策略.py` 或 `examples/B_跨期套利策略.py`（按需求二选一） |
| 第 3 节 移仓感知 | `examples/B_自动换月示例.py` |
| 第 4 节 Tick 驱动 | `examples/C_纯Tick限价单交易策略.py`、`examples/C_纯Tick高频交易策略.py` |
| 第 5 节 data_server + 订单流 | `examples/D_订单流与深度数据_data_server模式.py` |

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

| 相对路径（项目根下） | 类型 | 特点 / 关键词 |
|----------------------|------|----------------|
| `examples/B_双均线策略.py` | 回测 | 入门模板，完整注释 |
| `examples/B_自动换月示例.py` | 回测 | 移仓感知、auto_roll |
| `examples/B_自动参数示例.py` | 回测 | 参数优化遍历 |
| `examples/B_十大经典策略之Aberration.py` | 回测 | 布林通道 |
| `examples/B_日内交易策略.py` | 回测 | 日内平仓 |
| `examples/B_海龟交易策略.py` | 回测 | 海龟趋势；v0.4.4 修正示例逻辑 |
| `examples/B_加仓策略.py` | 回测 | 加仓、统计验证 |
| `examples/B_减仓策略.py` | 回测 | 分批减仓、统计验证 |
| `examples/B_正反手策略.py` | 回测 | `reverse_pos` |
| `examples/B_正反手混合开平仓策略.py` | 回测 | 开平仓与反手混合 |
| `examples/B_网格交易策略.py` | 回测 | 网格 |
| `examples/B_机器学习策略_随机森林.py` | 回测 | ML |
| `examples/B_多品种多周期交易策略.py` | 回测 | 多数据源、跨周期、`capital_ratio` |
| `examples/B_多品种多周期交易策略_参数优化.py` | 回测 | 同上策略的参数优化版 |
| `examples/B_跨期套利策略.py` | 回测 | 跨期价差 |
| `examples/B_跨品种套利策略.py` | 回测 | 跨品种价差 |
| `examples/B_强弱截面轮动策略.py` | 回测 | 截面轮动 |
| `examples/B_跨周期过滤策略.py` | 回测 | 大周期过滤 + 小周期执行 |
| `examples/C_纯Tick限价单交易策略.py` | 高级 | Tick、限价单 |
| `examples/C_纯Tick高频交易策略.py` | 高级 | Tick、高频 |
| `examples/C_期权交易策略.py` | 高级 | 期权 |
| `examples/C_期货期权组合策略.py` | 高级 | 期货+期权组合 |
| `examples/D_订单流与深度数据_data_server模式.py` | 数据 | data_server、订单流 |
| `examples/A_CTP连接状态监测测试_真实断网.py` | 工具 | 断网检测 |
| `examples/A_撤单重发示例.py` | 工具 | 撤单重发 |
| `examples/A_穿透式测试脚本.py` | 工具 | 穿透式认证 |
| `examples/A_工具_数据库管理_查看与删除.py` | 工具 | 本地 DB 管理 |
| `examples/A_工具_导入数据库DB示例.py` | 工具 | 导入 DB |

### 按需求快速选文件

| 需求 | 优先打开 |
|------|----------|
| 刚入门、跑通回测 | `examples/B_双均线策略.py` |
| 多品种、资金比例 | `examples/B_多品种多周期交易策略.py` |
| 反手、`reverse_pos` | `examples/B_正反手策略.py` |
| 移仓 | `examples/B_自动换月示例.py` |
| Tick / 高频 | `examples/C_纯Tick限价单交易策略.py` |
| data_server / 订单流 | `examples/D_订单流与深度数据_data_server模式.py` |
| CTP 连接与认证 | `examples/A_穿透式测试脚本.py` |
