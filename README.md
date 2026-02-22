# SSQuant - 期货量化交易框架

<div align="center">

🐿️ **松鼠Quant** | 专业的期货CTP量化交易框架
<img width="728" height="352" alt="image" src="https://github.com/user-attachments/assets/26201b06-0992-44dd-8416-03edcbb8878b" />

[![PyPI](https://img.shields.io/pypi/v/ssquant.svg)](https://pypi.org/project/ssquant/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Non--Commercial-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)]()

[GitHub](https://github.com/songshuquant/ssquant) | [Gitee（国内推荐）](https://gitee.com/ssquant/ssquant)

**一次编写，三处运行** - 回测 / SIMNOW模拟 / 实盘CTP

</div>

---

## 🎯 核心特性

### ✅ 统一的策略框架

- **一套代码三处运行** - 同一份策略代码可在回测、SIMNOW模拟、实盘CTP三种环境下运行
- **完整的数据支持** - K线数据（任意周期：1m/2m/5m/15m/30m/1h/4h/1d...）+ TICK逐笔数据
- **多品种多周期** - 同时交易多个品种，使用不同周期数据
- **跨平台支持** - 支持 Windows 和 Linux 系统

### ✅ 强大的交易功能

- **自动开平仓管理** - 智能识别开平仓、今昨仓
- **智能算法交易** - 支持限价单排队、超时撤单、追价重发等高级逻辑
- **实时回调系统** - on_trade/on_order/on_cancel 实时通知
- **TICK流双驱动** - K线驱动 + TICK驱动两种模式
- **断线自动重连** - CTP连接断开后自动重连，认证失败自动重试

### ✅ 灵活的数据获取

- **三种数据请求方式**：
  - 日期范围：`start_date` / `end_date`
  - 精确时间：`start_time` / `end_time`
  - K线数量：`limit`（获取最近N根K线）
- **本地K线派生** - 从1M自动派生任意周期（2M/7M/65M/120M等）
- **远程数据推送** - 支持 data_server WebSocket 实时K线推送

### ✅ 丰富的策略示例

- 19个完整策略示例
- 涵盖趋势、套利、轮动、期权、机器学习等类型
- 从入门到高级，循序渐进

---

## 📡 数据服务器（v0.4.2 重大升级）

### 🆕 全新 data_server 架构

v0.4.2 版本对远程数据服务进行了**重大升级**，新增独立的 `data_server` 数据服务器：

| 功能 | 说明 |
|------|------|
| **实时K线推送** | WebSocket 实时推送1分钟K线，毫秒级延迟 |
| **历史K线补全** | 连接时自动预加载历史K线，无缝衔接 |
| **订单流数据** | 新增12个订单流字段，支持量价分析策略 |
| **多周期派生** | 服务端1M推送 + 客户端任意周期聚合 |
| **断线自动重连** | 网络中断后自动重连，数据不丢失 |

### 📊 订单流数据字段

新增完整的订单流数据支持，可用于量价分析、主力资金追踪等策略：

```python
# 订单流字段（K线数据中自动包含）
'开仓'    # 总开仓量
'平仓'    # 总平仓量
'多开'    # 多头开仓
'空开'    # 空头开仓
'多平'    # 多头平仓
'空平'    # 空头平仓
'双开'    # 双开（多空同时开仓）
'双平'    # 双平（多空同时平仓）
'双换'    # 双换（换手）
'B'       # 主买量（Buy）
'S'       # 主卖量（Sell）
'未知'    # 未知方向
```

### 🔄 实时K线推送模式

```python
# 启用 data_server 实时K线推送
config = get_config(
    mode=RunMode.SIMNOW,
    symbol='rb2601',
    kline_period='1m',
    kline_source='data_server',  # 使用远程实时推送
)
```

**工作流程：**
1. 连接 data_server WebSocket 服务器
2. 自动预加载最近 N 根历史K线（可配置）
3. 实时接收1分钟K线推送
4. 客户端本地派生任意周期（5M/15M/1H/1D等）

---

## 🖥️ 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10+ / Linux (x86_64) |
| **Python** | 3.9 ~ 3.14 |
| **CTP版本** | 6.7.7 ~ 6.7.10 |
| **内存** | 4GB+ |

---

## ⚡ 快速开始

### 1. 安装及更新

**方式一：Git 更新（推荐）**

如果你是通过 `git clone` 安装的，可以用以下命令更新到最新版本：

```bash
# 1. 进入项目目录
cd ssquant

# 2. 拉取最新代码
git pull origin main

# 3. 重新安装（更新依赖）
pip install -e .
```

**完整的首次克隆 + 安装流程：**

```bash
# GitHub
git clone https://github.com/songshuquant/ssquant.git
cd ssquant
pip install -e .

# 或 Gitee（国内推荐，速度更快）
git clone https://gitee.com/ssquant/ssquant.git
cd ssquant
pip install -e .
```

> 💡 **提示**：使用 `pip install -e .`（开发模式）安装后，`git pull` 拉取的代码更新会立即生效，无需重复安装。

**方式二：下载压缩包重新安装**

如果你是下载源码压缩包安装的，需要重新下载最新版本：

1. 从 [GitHub Releases](https://github.com/songshuquant/ssquant/releases) 或 [Gitee](https://gitee.com/ssquant/ssquant) 下载最新压缩包
2. 解压到新目录
3. 进入目录执行安装：

```bash
cd ssquant-main
pip install -e .
```

**方式三：PyPI 更新**

```bash
pip install ssquant --upgrade
```

#### ❓ 常见问题：ModuleNotFoundError: No module named 'ssquant'

如果运行策略时遇到这个错误：

```
ModuleNotFoundError: No module named 'ssquant'
```

**原因**：ssquant 未安装或已被卸载。

**解决方法**：

1. 检查是否已安装：
   ```bash
   pip list | findstr ssquant   # Windows
   pip list | grep ssquant      # Linux
   ```

2. 如果没有找到，重新安装：
   ```bash
   pip install ssquant
   # 或从源码安装（在项目目录下执行）
   pip install -e .
   ```

3. 验证安装成功：
   ```bash
   python -c "from ssquant.api.strategy_api import StrategyAPI; print('ssquant 导入成功!')"
   ```

### 2. 配置账户

安装完成后，需要配置相关账户信息。编辑 `ssquant/config/trading_config.py`：

#### 📊 数据API配置（回测必需）

框架使用**松鼠俱乐部会员远程数据库**，会员填入账号密码后，回测和实盘自动预拉取数据到本地：

```python
# ========== 远程数据API认证 quant789.com(松鼠俱乐部会员) ==========
API_USERNAME = "你的会员账号"    # 鉴权账号 (您的俱乐部手机号或邮箱)
API_PASSWORD = "你的会员密码"    # 鉴权密码
```

> 💡 **非会员用户**：
> - 可自行修改远程服务器地址
> - 或参考 `examples/A_工具_导入数据库DB示例.py` 导入本地数据

#### 🔐 交易账户配置（模拟/实盘）

```python
# SIMNOW账户（模拟交易）
ACCOUNTS = {
    'simnow_default': {
        'investor_id': '你的SIMNOW账号',
        'password': '你的密码',
        'server_name': '电信1',  # 电信1/电信2/移动/TEST
        # ...
    },
    
    # 实盘账户
    'real_default': {
        'broker_id': '期货公司代码',
        'investor_id': '资金账号',
        'password': '密码',
        'md_server': 'tcp://xxx:port',
        'td_server': 'tcp://xxx:port',
        'app_id': 'AppID',
        'auth_code': '授权码',
        # ...
    },
}
```

### 3. 编写策略

```python
from ssquant.api.strategy_api import StrategyAPI
from ssquant.backtest.unified_runner import UnifiedStrategyRunner, RunMode
from ssquant.config.trading_config import get_config

def my_strategy(api: StrategyAPI):
    """双均线策略"""
    close = api.get_close()
    
    if len(close) < 20:
        return
    
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    pos = api.get_pos()
    
    # 金叉做多
    if ma5.iloc[-2] <= ma20.iloc[-2] and ma5.iloc[-1] > ma20.iloc[-1]:
        if pos <= 0:
            if pos < 0:
                api.buycover(order_type='next_bar_open')
            api.buy(volume=1, order_type='next_bar_open')
    
    # 死叉做空
    elif ma5.iloc[-2] >= ma20.iloc[-2] and ma5.iloc[-1] < ma20.iloc[-1]:
        if pos >= 0:
            if pos > 0:
                api.sell(order_type='next_bar_open')
            api.sellshort(volume=1, order_type='next_bar_open')

if __name__ == "__main__":
    # 回测配置
    config = get_config(
        mode=RunMode.BACKTEST,
        symbol='rb888',
        start_date='2025-01-01',
        end_date='2025-11-30',
        kline_period='1h',
        price_tick=1.0,
        contract_multiplier=10,
    )
    
    # 运行
    runner = UnifiedStrategyRunner(mode=RunMode.BACKTEST)
    runner.set_config(config)
    results = runner.run(strategy=my_strategy)
```

### 4. 多种数据请求方式

```python
# ===== 方式1：日期范围 =====
config = get_config(
    mode=RunMode.BACKTEST,
    symbol='rb888',
    start_date='2025-01-01',
    end_date='2025-11-30',
    kline_period='1h',
)

# ===== 方式2：精确时间范围 =====
config = get_config(
    mode=RunMode.BACKTEST,
    symbol='au888',
    kline_period='1m',
    start_time='2026-02-10 09:00:00',
    end_time='2026-02-14 15:00:00',
)

# ===== 方式3：获取最近N根K线 =====
config = get_config(
    mode=RunMode.BACKTEST,
    symbol='au888',
    kline_period='5m',
    limit=1000,  # 获取最近1000根K线
)

# ===== 方式4：从某日期开始取N根 =====
config = get_config(
    mode=RunMode.BACKTEST,
    symbol='au888',
    kline_period='5m',
    start_date='2026-01-01',
    limit=500,
)
```

### 5. 切换运行模式

```python
# ===== 回测模式 =====
config = get_config(
    mode=RunMode.BACKTEST,
    symbol='rb888',
    start_date='2025-01-01',
    end_date='2025-11-30',
    kline_period='1h',
)

# ===== SIMNOW模拟 =====
config = get_config(
    mode=RunMode.SIMNOW,
    account='simnow_default',      # 使用预配置的账户
    symbol='rb2601',               # 具体合约月份
    kline_period='1m',
)

# ===== 实盘交易 =====
config = get_config(
    mode=RunMode.REAL_TRADING,
    account='real_default',        # 使用预配置的账户
    symbol='rb2601',
    kline_period='1m',
)
```

**策略代码完全不用改！**

---

## 📚 文档导航

| 文档 | 说明 | 适合 |
|------|------|------|
| [用户手册.md](用户手册.md) | 📖 完整使用教程 | 新手必读 |
| [API参考手册.md](API参考手册.md) | 📚 详细API说明 | 开发查询 |
| [文档导航.md](文档导航.md) | 📑 所有文档索引 | 查找文档 |

---

## 🎓 示例策略

所有示例在 `examples/` 目录（共 **21个**，v0.4.2 新增 2个）：

### 工具类 (A_开头)

| 文件 | 说明 |
|------|------|
| `A_工具_导入数据库DB示例.py` | 数据导入数据库 |
| `A_工具_数据库管理_查看与删除.py` | 数据库管理 |
| `A_撤单重发示例.py` | 订单撤单重发机制 |
| `A_穿透式测试脚本.py` | CTP穿透式认证测试 |
| `A_CTP连接状态检测器_含实盘配置.py` | 🆕 CTP连接状态检测 |

### 策略类 (B_开头)

| 文件 | 说明 |
|------|------|
| `B_双均线策略.py` | ⭐ 经典均线交叉，入门推荐 |
| `B_海龟交易策略.py` | 唐奇安通道突破 |
| `B_十大经典策略之Aberration.py` | 布林带突破 |
| `B_日内交易策略.py` | 日内交易 |
| `B_网格交易策略.py` | 网格交易 |
| `B_强弱截面轮动策略.py` | 多品种强弱轮动 |
| `B_跨周期过滤策略.py` | 多周期信号过滤 |
| `B_跨品种套利策略.py` | 品种间价差套利 |
| `B_跨期套利策略.py` | 同品种跨期套利 |
| `B_多品种多周期交易策略.py` | 多品种多周期 |
| `B_多品种多周期交易策略_参数优化.py` | 参数优化示例 |
| `B_机器学习策略_随机森林.py` | ML机器学习预测 |
| `B_auto_params_demo.py` | 合约参数自动获取演示 |

### 高级类 (C_开头)

| 文件 | 说明 |
|------|------|
| `C_期权交易策略.py` | 期权交易 |
| `C_期货期权组合策略.py` | 期货期权组合 |
| `C_纯Tick高频交易策略.py` | TICK流高频交易 |
| `C_纯Tick限价单交易策略.py` | 🆕 限价单 + 智能追单演示 |

### 🆕 data_server 模式 (D_开头)

| 文件 | 说明 |
|------|------|
| `D_订单流与深度数据_data_server模式.py` | 🆕 **订单流数据交易策略** |

> **订单流策略说明**：
> - 利用 data_server 提供的 **12个订单流字段** 和 **盘口深度数据**
> - 多因子评分体系：订单流动量 + 主动买卖 + 资金流向 + 盘口压力
> - 仅 data_server 模式可用（本地聚合模式不包含订单流数据）

---

## 🤖 AI-Agent 智能助手

项目内置 **AI 量化策略编写助手**，帮助你快速生成、调试和优化交易策略。

### 功能特性

- 💬 **智能对话** - 用自然语言描述策略需求，AI 自动生成代码
- 📝 **代码生成** - 一键生成符合 ssquant 框架规范的策略代码
- 🔧 **一键回测** - 直接运行策略，实时查看回测输出和报告
- 🔄 **自动迭代** - AUTO模式下 AI 自动分析报告并优化策略

### 使用方法

> ⚠️ **重要提示**：
> - AI-Agent **不包含在 `pip install ssquant` 中**，需要 clone 仓库使用
> - `ai_agent` 目录**必须位于项目根目录下**，依赖 ssquant 框架运行

```bash
# 1. 克隆仓库
git clone https://github.com/songshuquant/ssquant.git
cd ssquant

# 2. 确保目录结构正确
# ssquant/          ← 项目根目录
# ├── ai_agent/     ← AI Agent
# ├── ssquant/      ← 核心框架（必需）
# └── examples/     ← 示例策略

# 3. 进入 ai_agent 目录并安装依赖
cd ai_agent
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 启动服务
python app.py

# 5. 打开浏览器访问 http://localhost:5000
# 6. 点击右上角 ⚙️ 配置 AI 模型 API Key
```

详细使用说明请查看 [ai_agent/README.md](ai_agent/README.md)

---

## 🏗️ 项目结构

```
ssquant-main/                   # 📁 项目根目录
├── ssquant/                    # 核心框架
│   ├── api/                    # 策略API
│   │   └── strategy_api.py     # 核心API类
│   ├── backtest/               # 回测引擎
│   │   ├── unified_runner.py   # 统一运行器
│   │   ├── backtest_core.py    # 回测核心
│   │   └── live_trading_adapter.py  # 实盘适配器
│   ├── config/                 # 配置管理
│   │   ├── trading_config.py   # 配置生成（账户配置在此）
│   │   └── _server_config.py   # data_server 连接配置
│   ├── data/                   # 数据管理
│   │   ├── api_data_fetcher.py # API数据获取
│   │   ├── local_data_loader.py # 本地数据加载
│   │   ├── ws_kline_client.py  # WebSocket K线客户端
│   │   ├── multi_period.py     # 多周期K线派生器
│   │   ├── auth_manager.py     # 鉴权管理器
│   │   └── local_adjust.py     # 本地复权模块
│   ├── ctp/                    # CTP二进制文件
│   │   ├── py39/ ~ py314/      # 各Python版本的CTP文件
│   │   │   ├── *.pyd / *.dll   # Windows 二进制
│   │   │   └── *.so            # Linux 二进制
│   │   └── loader.py           # CTP加载器（自动识别平台）
│   ├── pyctp/                  # CTP封装
│   │   ├── simnow_client.py    # SIMNOW客户端（断线重连）
│   │   └── real_trading_client.py  # 实盘客户端（断线重连）
│   └── indicators/             # 技术指标
│       └── tech_indicators.py
│
├── ai_agent/                   # 🤖 AI智能助手（独立工具）
│   ├── app.py                  # Flask Web应用
│   ├── templates/index.html    # 前端界面
│   ├── settings.json           # 配置文件
│   ├── requirements.txt        # 依赖清单
│   └── README.md               # 使用说明
│
├── examples/                   # 📚 策略示例（19个）
├── backtest_results/           # 📊 回测报告输出
├── backtest_logs/              # 📝 回测日志
└── data_cache/                 # 💾 数据缓存
```

---

## 💡 核心API

### 数据获取

```python
api.get_close()      # 收盘价序列
api.get_open()       # 开盘价序列
api.get_high()       # 最高价序列
api.get_low()        # 最低价序列
api.get_volume()     # 成交量序列
api.get_klines()     # 完整K线DataFrame
api.get_tick()       # 当前TICK数据（实盘）
```

### 持仓查询

```python
api.get_pos()        # 净持仓（正=多，负=空）
api.get_long_pos()   # 多头持仓
api.get_short_pos()  # 空头持仓
api.get_position_detail()  # 详细持仓（今昨仓）
```

### 交易操作

```python
api.buy(volume=1)         # 买入开仓
api.sell()                # 卖出平仓
api.sellshort(volume=1)   # 卖出开仓
api.buycover()            # 买入平仓
api.close_all()           # 全部平仓
api.reverse_pos()         # 反手
```

### 多数据源

```python
# 访问第2个数据源（index=1）
close = api.get_close(index=1)
api.buy(volume=1, index=1)
```

详见 [API参考手册.md](API参考手册.md)

---

## 🔧 系统要求

- **Python**: 3.9 ~ 3.14
- **系统**: Windows 10+ / Linux (x86_64)
- **内存**: 4GB+
- **网络**: 稳定连接（实盘/SIMNOW）

### CTP版本支持

框架内置 CTP 6.7.7 ~ 6.7.10 版本，位于 `ssquant/ctp/pyXXX/` 目录：

| Python版本 | 目录 | Windows | Linux |
|-----------|------|---------|-------|
| 3.9 | `py39/` | ✅ .pyd + .dll | ✅ .so |
| 3.10 | `py310/` | ✅ .pyd + .dll | ✅ .so |
| 3.11 | `py311/` | ✅ .pyd + .dll | ✅ .so |
| 3.12 | `py312/` | ✅ .pyd + .dll | ✅ .so |
| 3.13 | `py313/` | ✅ .pyd + .dll | ✅ .so |
| 3.14 | `py314/` | ✅ .pyd + .dll | ✅ .so |

### Linux 使用说明

Linux 系统首次使用时，框架会自动预加载 CTP 运行库。如遇问题，可手动设置：

```bash
export LD_LIBRARY_PATH=/path/to/ssquant/ctp/py3xx:$LD_LIBRARY_PATH
```

---

## ⚠️ 风险提示

本框架仅供学习和研究使用。期货交易有风险，入市需谨慎。

- ⚠️ 请先在SIMNOW充分测试（至少1周）
- ⚠️ 实盘前用小资金验证
- ⚠️ 做好风险管理和止损
- ⚠️ 不要使用高杠杆

---

## 📖 快速链接

- [PyPI 主页](https://pypi.org/project/ssquant/) - 安装和版本信息
- [GitHub 仓库](https://github.com/songshuquant/ssquant) - 源码和问题反馈
- [Gitee 仓库](https://gitee.com/ssquant/ssquant) - 国内推荐，访问更快
- [用户手册](用户手册.md) - 完整使用教程
- [API参考](API参考手册.md) - 所有API详解

---

## 📝 更新日志

### v0.4.2 (2026-02-22) 🚀 Linux支持 & 数据服务器重大升级

#### 📡 数据服务器升级（重点）

| 更新项 | 改进内容 | 效果 |
|-------|---------|------|
| **🆕 全新 data_server** | 独立数据服务器架构 | 更稳定、更快速的数据服务 |
| **📊 订单流数据** | 新增12个订单流字段 | 支持开仓/平仓/多开/空开/双开/B/S等 |
| **⚡ 实时K线推送** | WebSocket 毫秒级推送 | 实盘K线实时更新，无延迟 |
| **🔄 历史K线补全** | 连接时自动预加载 | 策略启动即有完整历史数据 |
| **📈 多周期本地派生** | 1M→任意周期聚合 | 支持 2M/7M/65M/120M 等任意周期 |

#### 🐧 平台与功能

| 更新项 | 改进内容 | 效果 |
|-------|---------|------|
| **Linux 平台支持** | 新增 CTP Linux 二进制文件 (.so) | 支持在 Linux 服务器运行实盘 |
| **鉴权管理** | 新增 auth_manager 模块 | 通过 data_server 代理验证身份 |
| **精确时间请求** | start_time/end_time/limit 参数 | 三种数据请求方式灵活组合 |
| **断线重连优化** | 认证失败自动重试，详细日志 | CTP 连接稳定性大幅提升 |
| **日线归属修复** | 凌晨夜盘归属前一自然日 | 日线聚合逻辑更准确 |

详细更新内容请查看 [042.MD](042.MD)

### v0.4.1 (2026-02-04) 🐛 平今平昨Bug修复

| 更新项 | 改进内容 | 效果 |
|-------|---------|------|
| **🐛 昨仓识别修复** | 修复上期所/能源中心 `YdPosition` 返回不可靠的问题 | 昨仓计算改为 `Position - TodayPosition` |
| **📁 修改文件** | `simnow_client.py`, `real_trading_client.py`, `live_trading_adapter.py` | 3个文件，约15行代码 |
| **✅ 解决问题** | 不再出现"错误50: 平今仓位不足"的错误 | SHFE/INE品种平仓正常 |

详细更新内容请查看 [更新日志_v0.4.1.md](更新日志_v0.4.1.md)

### v0.4.0 (2026-01) 🎯 合约参数自动获取

| 更新项 | 改进内容 | 效果 |
|-------|---------|------|
| **📦 合约信息服务** | 新增 `contract_info.py` 自动获取合约参数 | 无需手动填写乘数、跳动、保证金率 |
| **⚙️ 配置升级** | `get_config()` 新增 `auto_params` 参数 | 只需合约代码，其他自动获取 |
| **💰 账户查询** | 新增 `api.get_balance()` 等账户方法 | 回测/实盘统一查询接口 |
| **🔧 数据库优化** | 线程安全写入 + 快速追加 K线 | 多线程并发稳定性提升 |
| **🔄 实盘适配器** | K线聚合逻辑修复 + 代码重构 | 历史数据预加载后状态一致性 |

详细更新内容请查看 [更新日志_v0.4.0.md](更新日志_v0.4.0.md)

### v0.3.9 (2026-01) 🚀 重大升级

本次更新涵盖**回测引擎优化**、**报告系统重构**和**AI智能助手**三大核心模块：

| 更新项 | 改进内容 | 效果 |
|-------|---------|------|
| **🤖 AI-Agent** | 新增 AI 量化策略编写助手 | 自然语言生成策略代码 |
| **数据对齐函数** | 完善 `align_data` 多数据源时间对齐机制 | 多周期/多品种策略数据同步 |
| **数据窗口控制** | 新增 `lookback_bars` 滑动窗口参数 | 内存占用降低 90%+ |
| **回测速度提升** | 修复数据累积导致的性能下降问题 | 速度稳定，不再逐步下降 |
| **报告生成速度** | Plotly 替换 matplotlib | 生成速度提升 **5-10 倍** |
| **报告系统重制** | 全新交互式 HTML 报告 | 支持缩放、拖拽、多图对比 |

详细更新内容请查看 [更新日志_2026-01-06.md](更新日志_2026-01-06.md)

### v0.3.7 (2025-12)

- 🔄 移除构建脚本和冗余文件
- ✅ 修复 CTP 登录报错乱码问题
- ✅ 优化项目结构

### v0.3.6 (2025-12)

- ✅ 修复 CTP 登录报错乱码问题 (Windows下GBK/GB18030解码)
- ✅ 优化 SIMNOW 和实盘客户端的错误信息显示

### v0.3.0 (2025-12)

- ✅ 完整的TICK流双驱动模式
- ✅ 多品种多周期支持
- ✅ 订单撤单重发机制
- ✅ 实时回调系统（on_trade/on_order/on_cancel）
- ✅ 动态price_tick和offset_ticks
- ✅ 统一的API接口
- ✅ 19个策略示例

---

**开始你的量化交易之旅！** 🚀

查看 [用户手册.md](https://github.com/songshuquant/ssquant/blob/main/%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C.md) 了解详细使用方法。
