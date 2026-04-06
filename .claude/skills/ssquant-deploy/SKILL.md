---
name: ssquant-deploy
description: 将 SSQuant 策略从回测部署到 SIMNOW 仿真和实盘交易
version: 0.4.4
tags: [quant, futures, ctp, deployment, simnow, live-trading]
author: SSQuant Team
---

# SSQuant 部署上线技能

## 你是什么

你是一个专业的期货策略部署助手，能够帮助用户将回测验证过的策略安全地部署到 SIMNOW 仿真环境和实盘环境。

框架 **v0.4.4**；`kline_source='data_server'` 时的连接与备用说明见 **`更新日志_v0.4.4.md`** 与 `ssquant-data` 技能。

## 部署路径

```
回测验证 → SIMNOW 仿真 → 实盘交易
```

三个阶段使用 **同一个策略函数**，仅切换 `RunMode` 和账户配置。

## 阶段一：SIMNOW 仿真部署

### 1. 申请 SIMNOW 账号

- 在 [SIMNOW官网](http://www.simnow.com.cn/) 注册
- 获取 `investor_id` 和 `password`

### 2. 修改配置

```python
from ssquant.config.trading_config import get_config, RunMode

config = get_config(
    RunMode.SIMNOW,
    account="simnow_default",
    symbol="rb2510",             # 使用真实合约，非888
    kline_period="1m",
    investor_id="你的SIMNOW账号",
    password="你的SIMNOW密码",
    server_name="电信1",          # 电信1/电信2/移动/TEST/24hour
    preload_history=True,
    history_lookback_bars=200,
    order_offset_ticks=2,
    auto_params=True,
    params=PARAMS,
)
```

### 3. 添加实盘回调

```python
from ssquant.backtest.unified_runner import UnifiedStrategyRunner

runner = UnifiedStrategyRunner(config)
runner.run(
    strategy,
    initialize=initialize,
    on_trade=on_trade,           # 成交回报
    on_order=on_order,           # 委托回报
    on_disconnect=on_disconnect, # 断线回调
)

def on_trade(trade_info):
    print(f"成交: {trade_info}")

def on_order(order_info):
    print(f"委托: {order_info}")

def on_disconnect(reason):
    print(f"断线: {reason}")
```

### 4. SIMNOW 服务器选择

| 服务器 | 交易时段 | 用途 |
|--------|---------|------|
| `电信1` | 交易时段 | 正式仿真 |
| `电信2` | 交易时段 | 备用 |
| `移动` | 交易时段 | 移动网络 |
| `TEST` | 交易时段 | 测试 |
| `24hour` | 全天候 | 7×24 小时测试 |

## 阶段二：实盘部署

### 1. 准备实盘账户信息

从期货公司获取以下信息：

- `broker_id`: 期货公司代码
- `investor_id`: 资金账号
- `password`: 交易密码
- `md_server`: 行情前置地址
- `td_server`: 交易前置地址
- `app_id`: 穿透式认证 AppID
- `auth_code`: 穿透式认证 AuthCode

### 2. 实盘配置

```python
config = get_config(
    RunMode.REAL_TRADING,
    account="real_default",
    symbol="rb2510",
    kline_period="1m",
    broker_id="期货公司代码",
    investor_id="资金账号",
    password="交易密码",
    md_server="tcp://行情前置地址:端口",
    td_server="tcp://交易前置地址:端口",
    app_id="穿透式AppID",
    auth_code="穿透式AuthCode",
    order_offset_ticks=2,
    auto_params=True,
    params=PARAMS,
)
```

### 3. 实盘安全清单

- [ ] SIMNOW 仿真运行 ≥ 1 周无异常
- [ ] 确认合约代码正确（非连续合约 888/777）
- [ ] 确认资金充足（保证金 + 手续费 + 缓冲）
- [ ] 确认交易时段正确
- [ ] 设置 `order_timeout` 和 `retry_limit`
- [ ] 实现 `on_disconnect` 断线处理
- [ ] 实现 `on_trade` / `on_order` 监控
- [ ] 测试 CTP 穿透式认证（`A_穿透式测试脚本.py`）
- [ ] 小手数试运行 ≥ 3 个交易日

## 自动移仓配置

实盘中使用连续合约时需要自动移仓：

```python
config = get_config(
    RunMode.REAL_TRADING,
    symbol="rb2510",
    auto_roll_enabled=True,
    auto_roll_mode="simultaneous",     # 或 "sequential"
    auto_roll_reopen=True,
    auto_roll_order_type="limit",
    auto_roll_close_offset_ticks=2,
    auto_roll_open_offset_ticks=2,
    auto_roll_verify_timeout_bars=10,
    auto_roll_log_enabled=True,
    # ...其他账户参数
)
```

策略中需添加移仓感知：

```python
def strategy(api):
    if api.is_rollover_busy():
        return  # 移仓期间不下单
```

## data_server 模式部署

```python
config = get_config(
    RunMode.SIMNOW,
    kline_source="data_server",        # 使用远程 K 线推送
    enable_tick_callback=True,
    tick_callback_interval=0.5,        # 防开盘洪峰
    tick_queue_maxsize=20000,
    # ...
)
```

## 算法交易（撤单重发）

```python
config = get_config(
    RunMode.SIMNOW,
    algo_trading=True,
    order_timeout=30,       # 30秒未成交触发撤单
    retry_limit=3,          # 最多重发3次
    retry_offset_ticks=1,   # 每次重发追价1个tick
    # ...
)
```

## 运行时回调一览

| 回调 | 参数 | 触发时机 |
|------|------|---------|
| `on_trade` | trade_info | 成交回报 |
| `on_order` | order_info | 委托回报 |
| `on_cancel` | cancel_info | 撤单确认 |
| `on_order_error` | error_info | 报单错误 |
| `on_cancel_error` | error_info | 撤单错误 |
| `on_account` | account_info | 账户更新 |
| `on_position` | position_info | 持仓更新 |
| `on_position_complete` | — | 持仓查询完成 |
| `on_disconnect` | reason | 连接断开 |
| `on_query_trade` | trade | 查询成交 |
| `on_query_trade_complete` | — | 成交查询完成 |

## CTP 版本支持

- 6.7.7 及以上所有版本
- Windows x64 + Linux x64
- Python 3.9–3.14

## 注意事项

1. **实盘必须使用具体合约**（如 `rb2510`），不能用 `rb888`
2. **CTP 查询限频**: `query_account()` / `query_position()` 后需等待 0.3-0.5 秒
3. **断线重连**: 框架自动重连，但策略应通过 `on_disconnect` 记录日志
4. **穿透式认证**: 实盘必须通过穿透式认证，先用 `A_穿透式测试脚本.py` 验证
5. **敏感信息**: 密码和服务器地址不要硬编码在策略文件中，建议使用环境变量或配置文件
