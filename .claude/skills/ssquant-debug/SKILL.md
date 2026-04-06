---
name: ssquant-debug
description: 诊断和排查 SSQuant 框架中的 CTP 连接、数据、策略和交易问题
version: 0.4.4
tags: [quant, futures, ctp, debugging, troubleshooting]
author: SSQuant Team
---

# SSQuant 问题诊断技能

## 你是什么

你是一个专业的期货量化系统诊断助手，能够系统性地排查 SSQuant 框架在回测、仿真和实盘中遇到的各类问题。

**框架 v0.4.4**：发布说明见 **`更新日志_v0.4.4.md`**。

## 诊断流程

```
1. 确认运行模式（回测/SIMNOW/实盘）
2. 分类问题类型
3. 检查对应排查清单
4. 给出修复方案
```

## 问题分类与排查

### 一、CTP 连接问题

#### 症状: 连接失败 / 登录失败

**排查清单:**
1. 检查网络连通性
2. 确认 SIMNOW 服务器是否在交易时段（除 `24hour` 外）
3. 确认 `investor_id` / `password` 正确
4. 实盘: 确认 `broker_id`, `md_server`, `td_server` 正确
5. 实盘: 确认穿透式认证 `app_id` / `auth_code` 已配置

**常见错误码:**

| 断线原因码 | 含义 |
|-----------|------|
| `0x1001` | 网络读失败 |
| `0x1002` | 网络写失败 |
| `0x2001` | 心跳超时 |
| `0x2002` | 发送心跳失败 |
| `0x2003` | 收到错误报文 |

**修复方案:**
```python
# 检查 CTP 是否可用
from ssquant import CTP_AVAILABLE
print(f"CTP 可用: {CTP_AVAILABLE}")

# 使用穿透式测试脚本验证
# 参考 examples/A_穿透式测试脚本.py
```

#### 症状: 频繁断线重连

- 检查网络稳定性
- 确认 `tick_callback_interval` ≥ 0.5（防止回调风暴）
- 检查 `tick_queue_maxsize` 是否足够（默认 20000）
- 实现 `on_disconnect` 回调记录断线原因

### 二、数据问题

#### 症状: K 线数据为空

**排查清单:**
1. 检查 `symbol` 拼写（小写，如 `rb888` 不是 `RB888`）
2. 检查 `start_date` / `end_date` 范围内是否有交易日
3. 检查 `kline_period` 格式（`1m/5m/15m/30m/1h/1d`）
4. 检查网络 / API 认证（`API_USERNAME` / `API_PASSWORD`）
5. 尝试 `use_cache=False` 排除缓存问题

#### 症状: 鉴权通过但回测仍提示 data_server 无法获取数据（v0.4.4 前常见）

**原因**：旧版历史 K 线请求可能未遍历 `fallback_servers`，与鉴权端点不一致。

**处理**：升级到 **v0.4.4+**；并检查 `ssquant/config/_server_config.py`（或账户 `data_server`）中 **`api_url` 与 `fallback_servers` 是否指向可提供服务且库内有合约数据**的节点。

#### 症状: 数据有缺失或跳跃

- 确认 `adjust_type` 设置（复权切换会导致价格不连续）
- data_server 模式: 检查 WebSocket 连接状态
- 尝试 `use_cache=False` 重新获取

#### 症状: data_server 模式开盘卡顿

**原因:** 集合竞价和开盘瞬间 Tick 洪峰

**修复:**
```python
config = get_config(
    ...,
    kline_source="data_server",
    enable_tick_callback=True,
    tick_callback_interval=0.5,    # 关键: 限制回调频率
    tick_queue_maxsize=20000,      # 有界队列防内存溢出
)
```

#### 症状: 复权价格异常

- `get_price()` 返回复权后价格，`get_raw_price()` 返回原始价格
- 确认 `adjust_type` 是否正确: `'0'`不复权 / `'1'`后复权 / `'2'`前复权
- 检查连续合约切换点的复权因子

### 三、策略逻辑问题

#### 症状: 策略不发信号

**排查清单:**
1. 添加 `api.log()` 在关键判断点输出调试信息
2. 检查数据长度: `len(klines) >= 所需最小周期`
3. 检查条件是否过于严格
4. 启用 `debug=True` 查看详细日志

```python
def strategy(api):
    klines = api.get_klines()
    api.log(f"K线数量: {len(klines)}, 持仓: {api.get_pos()}")

    # 在每个条件分支加日志
    if condition_a:
        api.log("条件A满足")
    else:
        api.log(f"条件A不满足: value={value}")
```

#### 症状: 重复开仓 / 意外锁仓

- 检查是否在开仓前先检查了持仓: `if pos <= 0: api.buy()`
- 确认先平后开: 反向开仓前先平掉反向持仓
- 检查 `is_rollover_busy()` — 移仓期间可能导致持仓状态混乱

#### 症状: 回测资金不足

```
[REJECT] 开仓被拒: 资金不足
```

- 增加 `initial_capital`
- 减少单次交易 `volume`
- 检查 `margin_rate` 和 `contract_multiplier`
- 启用 `debug=True` 查看资金流水

### 四、交易执行问题

#### 症状: 下单失败

**排查清单:**
1. 确认交易时段（非交易时段 CTP 拒绝报单）
2. 检查 `order_type` 是否支持当前模式
3. 实盘: 确认资金充足、合约可交易
4. 检查是否触发了 CTP 流控

#### 症状: 撤单失败

- CTP 有撤单频率限制
- `cancel_all_orders()` 后等待 0.3-0.5 秒再下新单
- 检查订单是否已经成交（终态订单不可撤）

#### 症状: 移仓异常

**排查清单:**
1. 检查 `auto_roll_enabled` 是否为 `True`
2. 检查 `auto_roll_mode`: `simultaneous` vs `sequential`
3. 查看移仓审计日志: `live_data/rollover_logs/rollover_YYYYMMDD.log`
4. 检查 `auto_roll_verify_timeout_bars` 是否太小
5. 确认策略中是否正确使用 `is_rollover_busy()` 跳过信号

```python
# 查看移仓状态
status = api.get_rollover_status()
api.log(f"移仓状态: {status}")
```

### 五、性能问题

#### 症状: 策略运行缓慢

**排查清单:**
1. 减少 `lookback_bars`（大 DataFrame 拖慢计算）
2. 避免在 `strategy()` 中做重复计算
3. 使用 `get_runtime_stats()` 检查队列积压

```python
stats = api.get_runtime_stats()
api.log(f"运行时: {stats}")

if api.is_runtime_under_pressure("critical"):
    api.log("系统高压！考虑简化策略逻辑")
```

#### 症状: 内存持续增长

- 设置 `lookback_bars` 限制 K 线窗口
- 确认 `tick_queue_maxsize` 有界
- 避免在策略中累积大量数据

## 调试工具

### 启用调试模式

```python
config = get_config(
    ...,
    debug=True,  # 输出详细日志
)
```

### 运行时诊断 API

```python
def strategy(api):
    # 运行时状态
    stats = api.get_runtime_stats()
    pressure = api.get_runtime_pressure()

    # 账户状态（实盘）
    account = api.get_account()

    # 持仓详情
    detail = api.get_position_detail()

    # 移仓状态
    roll_status = api.get_rollover_status()
    is_rolling = api.is_rollover_busy()

    api.log(f"压力: {pressure} | 持仓: {detail} | 移仓: {is_rolling}")
```

### CTP 连接测试

参考 `examples/A_CTP连接状态监测测试_真实断网.py` 进行网络断线测试。

### 数据库管理

参考 `examples/A_工具_数据库管理_查看与删除.py` 查看和清理本地缓存数据。

## 常见错误速查表

| 错误 | 原因 | 解决 |
|------|------|------|
| `CTP功能不可用` | 平台/Python版本不支持CTP | 确认 Win64/Linux64 + Python 3.9-3.14 |
| `verify_auth() 失败` | API 认证失败 | 检查 `API_USERNAME` / `API_PASSWORD` |
| `Login failed` | CTP 登录失败 | 检查账号密码和服务器地址 |
| `No data returned` | 数据为空 | 检查 symbol、日期、网络 |
| `[REJECT] 资金不足` | 保证金不够 | 增加资金或减少手数 |
| `Queue full` | Tick 队列满 | 增加 `tick_queue_maxsize` 或加 `tick_callback_interval` |
| `Rollover timeout` | 移仓超时 | 增加 `auto_roll_verify_timeout_bars` |
| `Disconnect 0x2001` | 心跳超时 | 检查网络稳定性 |
