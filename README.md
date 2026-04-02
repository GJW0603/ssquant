# SSQuant - 期货量化交易框架

<div align="center">

🐿️ **松鼠Quant** | 专业的期货CTP量化交易框架
<img width="728" height="352" alt="image" src="https://github.com/user-attachments/assets/26201b06-0992-44dd-8416-03edcbb8878b" />

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Non--Commercial-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)]()

[GitHub](https://github.com/songshuquant/ssquant) | [Gitee（国内推荐）](https://gitee.com/ssquant/ssquant)

**一次编写，三处运行** - 回测 / SIMNOW模拟 / 实盘CTP

</div>

---

## 🤖 AI Agent.SKILLS 技能集成

SSQuant 内置了 [SKILL.md](https://github.com/anthropics/skill-md) 开放标准的 AI 智能体技能，支持 Claude Code、Cursor、Codex、Gemini CLI 等 AI 编程助手 **直接理解并操作** SSQuant 框架。

| 技能 | 路径 | 能力 |
|------|------|------|
| **策略编写** | `.claude/skills/ssquant-strategy/` | 编写符合框架规范的期货策略，包含 API 参考和示例 |
| **回测验证** | `.claude/skills/ssquant-backtest/` | 配置回测参数、执行回测、参数优化 |
| **部署上线** | `.claude/skills/ssquant-deploy/` | SIMNOW 仿真 → 实盘部署全流程 |
| **问题诊断** | `.claude/skills/ssquant-debug/` | 排查 CTP 连接、数据、策略、交易异常 |
| **数据查询** | `.claude/skills/ssquant-data/` | 行情、持仓、账户、订单流数据查询 |

在支持 SKILL.md 的 AI 编程助手中打开 SSQuant 项目，即可通过自然语言完成策略编写、回测、部署、调试全流程。项目级 AI 上下文见 [AGENTS.md](AGENTS.md)。

---

## 🎯 核心特性

### ✅ 统一的策略框架

- **一套代码三处运行** - 同一份策略代码可在回测、SIMNOW模拟、实盘CTP三种环境下运行
- **完整的数据支持** - K线数据（任意周期：1m/2m/5m/15m/30m/1h/4h/1d...）+ TICK逐笔数据
- **多品种多周期** - 同时交易多个品种，使用不同周期数据
- **跨平台支持** - 支持 Windows 和 Linux (x86_64) 系统

### ✅ 强大的交易功能

- **自动开平仓管理** - 智能识别开平仓、今昨仓，强平自动处理
- **智能算法交易** - 支持限价单排队、超时撤单、追价重发等高级逻辑
- **自动移仓引擎** - 主力合约换月时自动平旧开新，支持同时/顺序两种模式
- **实时回调系统** - on_trade/on_order/on_cancel 实时通知
- **TICK流双驱动** - K线驱动 + TICK驱动两种模式，data_server 模式实时推送深度数据K线
- **断线自动重连** - CTP连接断开后自动重连，认证失败自动重试，WebSocket 鉴权自动恢复
- **实盘抗压机制** - Tick 有界队列 + 水位控制 + 积压压缩 + 压力等级感知

### ✅ 灵活的数据获取

- **三种数据请求方式**：
  - 日期范围：`start_date` / `end_date`
  - 精确时间：`start_time` / `end_time`
  - K线数量：`limit`（获取最近N根K线）
- **本地K线派生** - 从1M自动派生任意周期（2M/7M/65M/120M等）
- **远程数据推送** - 支持 data_server WebSocket 实时K线推送
- **本地复权计算** - 支持前复权/后复权，基于合约切换点比例因子算法

### ✅ 回测引擎

- **资金约束** - 开仓按可用资金校验，待执行订单资金预占，资金不足自动裁剪手数
- **智能停止** - 资金耗尽且无持仓时提前终止回测，避免空跑
- **拒单可见** - 资金不足等关键信息即使 `debug=False` 也会在控制台显示

### ✅ 丰富的策略示例

- 24个完整策略示例，注释全面重写为用户友好风格
- 涵盖趋势、套利、轮动、期权、机器学习、自动移仓等类型
- 从入门到高级，循序渐进

---

## 📡 数据服务器

### 全新 data_server 架构

远程数据服务独立的 `data_server` 数据服务器：

| 功能 | 说明 |
|------|------|
| **实时K线推送** | WebSocket 实时推送K线，毫秒级延迟 |
| **历史K线补全** | 连接时自动预加载历史最新K线，无缝衔接 |
| **订单流数据** | 新增12个订单流字段，支持量价分析策略 |
| **多周期支持** | 服务端直接推送任意周期K线（1M/5M/15M/1H/1D等） |
| **断线自动重连** | 网络中断后自动重连并重新鉴权，数据不丢失 |
| **开盘假死修复** | data_server + Tick回调模式下智能节流，解决开盘积压 |

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
3. 实时接收订阅周期的K线推送（支持1M/5M/15M/30M/1H/1D等）
4. 无需本地聚合，服务端直接推送目标周期

---

## 🔄 自动移仓引擎（v0.4.3 新增）

主力合约换月时，框架自动完成移仓（平旧合约 → 开新主力），无需在策略里手写换月逻辑。

### 两种模式

| 模式 | 说明 |
|------|------|
| `simultaneous`（默认） | 同一次回调内平旧 + 开新，不等成交，速度更快 |
| `sequential` | 先平旧，旧腿平仓确认后再开新，更稳妥 |

### 使用方式

```python
config = get_config(
    mode=RunMode.SIMNOW,
    symbol='rb888',           # 888 = 自动映射当前主力
    kline_period='15m',
    auto_roll_enabled=True,   # 开启自动移仓
    auto_roll_reopen=True,    # 平旧后自动在新主力开仓
    auto_roll_mode='simultaneous',  # 移仓模式
)
```

### 策略内查询

```python
def strategy(api):
    if api.is_rollover_busy():
        return  # 移仓进行中，暂停交易信号
    status = api.get_rollover_status()
```

> 仅 SIMNOW / 实盘生效，回测模式下不执行自动移仓。默认开启复盘日志（`./live_data/rollover_logs/`）。

---

## 📐 本地复权算法（v0.4.3 新增）

data_server 只存储不复权（raw）数据，复权计算在框架本地完成。

通过 `real_symbol` 列检测合约切换点，在切换点计算比例因子自动调整 OHLC 价格。

```python
from ssquant.data import get_futures_data

df = get_futures_data('au888', '1D', adjust_type='1', limit=300)  # 后复权
df = get_futures_data('au888', '1D', adjust_type='2', limit=300)  # 前复权
```

| 类型 | 参数 | 说明 |
|------|------|------|
| 不复权 | `adjust_type='0'` | 原始价格，默认 |
| 后复权 | `adjust_type='1'` | 最早数据保持原价，后续累积因子调整 |
| 前复权 | `adjust_type='2'` | 最新数据保持原价，历史数据反向调整 |

---

## 🖥️ 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10+ / Linux (x86_64) |
| **Python** | 3.9 ~ 3.14 |
| **CTP版本** | >=6.7.7 版本 |
| **内存** | 4GB+ |

---

## ⚡ 快速开始

### 1. 安装及更新

> ⚠️ **重要提示**：从 v0.4.3 起，**不再支持 `pip install ssquant` 安装和更新**。由于包含 CTP 二进制文件（.pyd/.dll/.so），包体积超过 PyPI 限制，必须通过 **Git 仓库** 或 **下载源码压缩包** 的方式安装。已通过 pip 安装的旧版本请先卸载：`pip uninstall ssquant`，然后按以下方式重新安装。

**方式一：Git 克隆 + 更新（推荐）**

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

2. 如果没有找到，从源码安装（在项目目录下执行）：
   ```bash
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
    config = get_config(
        mode=RunMode.BACKTEST,
        symbol='rb888',
        start_date='2025-01-01',
        end_date='2025-11-30',
        kline_period='1h',
    )
    
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
    limit=1000,
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
    account='simnow_default',
    symbol='rb888',             # 888 自动映射当前主力合约
    kline_period='1m',
    auto_roll_enabled=False,    # 需要自动移仓时设为 True
)

# ===== 实盘交易 =====
config = get_config(
    mode=RunMode.REAL_TRADING,
    account='real_default',
    symbol='rb888',
    kline_period='1m',
    auto_roll_enabled=False,
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

所有示例在 `examples/` 目录（共 **25个**），v0.4.3 全部示例注释重写为面向用户的简洁说明：

### 工具类 (A_开头)

| 文件 | 说明 |
|------|------|
| `A_工具_导入数据库DB示例.py` | 数据导入数据库 |
| `A_工具_数据库管理_查看与删除.py` | 数据库管理 |
| `A_撤单重发示例.py` | 订单撤单重发机制 |
| `A_穿透式测试脚本.py` | CTP穿透式认证测试 |
| `A_CTP连接状态监测测试_真实断网.py` | 🆕 CTP连接状态异常监测（真实断网测试） |

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
| `B_自动参数示例.py` | 合约参数自动获取演示 |
| `B_自动换月示例.py` | 🆕 **自动移仓 + 双均线**，演示主力换月自动平旧开新 |

### 高级类 (C_开头)

| 文件 | 说明 |
|------|------|
| `C_期权交易策略.py` | 期权交易 |
| `C_期货期权组合策略.py` | 期货期权组合 |
| `C_纯Tick高频交易策略.py` | TICK流高频交易 |
| `C_纯Tick限价单交易策略.py` | 限价单 + 智能追单演示 |

### data_server 模式 (D_开头)

| 文件 | 说明 |
|------|------|
| `D_订单流与深度数据_data_server模式.py` | **订单流数据交易策略** |

> **订单流策略说明**：
> - 利用 data_server 提供的 **12个订单流字段** 和 **盘口深度数据**
> - 多因子评分体系：订单流动量 + 主动买卖 + 资金流向 + 盘口压力
> - 仅 data_server 模式可用（本地聚合模式不包含订单流数据）

### 示例注释规范（v0.4.3）

所有示例的文件头 docstring 和配置区注释已统一重写：

```
合约代码 symbol 怎么填：
  回测：品种+888 = 主力连续合约（如 au888、rb888）
  SIMNOW / 实盘：
    au888  → 自动映射为当前主力月份（如 au888→au2508）
    au777  → 自动映射为次主力月份
    au2508 → 指定月份，直接使用

自动移仓：auto_roll_enabled=True 即可自动平旧开新
合约参数：乘数、最小变动价、手续费等自动获取
复权：'0'=不复权  '1'=后复权  '2'=前复权
K线来源：'local'=本地CTP Tick合成  'data_server'=远程推送
```

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
│   │   ├── strategy_api.py     # 核心API类（含运行时压力/移仓状态查询）
│   │   └── debug_utils.py      # 调试工具
│   ├── backtest/               # 回测引擎
│   │   ├── unified_runner.py   # 统一运行器
│   │   ├── backtest_core.py    # 回测核心（资金约束、拒单摘要）
│   │   ├── backtest_logger.py  # 回测日志（含 log_important）
│   │   ├── live_trading_adapter.py  # 实盘适配器（Tick队列抗压、节流）
│   │   ├── rollover_engine.py  # 🆕 自动移仓引擎
│   │   └── rollover_audit.py   # 🆕 移仓复盘日志
│   ├── config/                 # 配置管理
│   │   ├── trading_config.py   # 配置生成（账户配置在此）
│   │   └── _server_config.py   # data_server 连接配置
│   ├── data/                   # 数据管理
│   │   ├── api_data_fetcher.py # API数据获取
│   │   ├── data_source.py      # 数据源（资金校验、预占）
│   │   ├── local_data_loader.py # 本地数据加载
│   │   ├── ws_kline_client.py  # WebSocket K线客户端（鉴权恢复）
│   │   ├── multi_period.py     # 多周期K线派生器
│   │   ├── auth_manager.py     # 鉴权管理器
│   │   ├── local_adjust.py     # 🆕 本地复权模块（前复权/后复权）
│   │   ├── contract_info.py    # 合约信息服务
│   │   └── contract_mapper.py  # 合约映射器
│   ├── ctp/                    # CTP二进制文件
│   │   ├── py39/ ~ py314/      # 各Python版本的CTP文件
│   │   │   ├── *.pyd / *.dll   # Windows 二进制
│   │   │   └── *.so            # Linux 二进制
│   │   └── loader.py           # CTP加载器（自动识别平台）
│   ├── pyctp/                  # CTP封装
│   │   ├── simnow_client.py    # SIMNOW客户端（断线重连）
│   │   └── real_trading_client.py  # 实盘客户端（断线重连 + is_ready）
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
├── examples/                   # 📚 策略示例（25个）
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

### 运行时状态（v0.4.3 新增）

```python
api.get_runtime_stats()        # 运行时统计（队列长度、处理耗时等）
api.get_runtime_pressure()     # 压力等级：normal / busy / critical
api.is_runtime_under_pressure() # 是否处于高压状态
api.is_rollover_busy()         # 是否正在移仓
api.get_rollover_status()      # 移仓详细状态
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

框架支持 CTP 6.7.7 及以上版本，CTP 文件位于 `ssquant/ctp/pyXXX/` 目录：

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

- [GitHub 仓库](https://github.com/songshuquant/ssquant) - 源码和问题反馈
- [Gitee 仓库](https://gitee.com/ssquant/ssquant) - 国内推荐，访问更快
- [用户手册](用户手册.md) - 完整使用教程
- [API参考](API参考手册.md) - 所有API详解

---

## 📝 更新日志

### v0.4.3 (2026-04-02) 🚀 自动移仓 & 实盘抗压 & 回测资金约束

#### 🔄 自动移仓引擎（重点新功能）

| 更新项 | 说明 |
|-------|------|
| **🆕 自动移仓** | 主力换月时自动平旧开新，支持 simultaneous / sequential 两种模式 |
| **🆕 移仓复盘日志** | 每笔移仓操作记录到本地日志，支持 JSON Lines 格式 |
| **🆕 策略查询接口** | `api.is_rollover_busy()` / `api.get_rollover_status()` |
| **🔧 旧合约匹配修复** | 平旧合约时按「新主力或旧合约」统一匹配，撤单使用实际合约代码 |

#### 📐 本地复权算法（新功能）

| 更新项 | 说明 |
|-------|------|
| **🆕 前复权/后复权** | 基于合约切换点比例因子的本地复权算法 |
| **配置开关** | `ENABLE_REMOTE_ADJUST` / `adjust_type` 参数控制 |

#### 💪 实盘抗压增强

| 更新项 | 说明 |
|-------|------|
| **Tick 有界队列** | 新增 `tick_queue_maxsize`，队列满时按品种缓存最新 Tick |
| **水位控制** | 软水位 + 恢复水位，高压时自动压缩积压数据 |
| **压力等级** | `normal` → `busy` → `critical`，策略可感知并主动降级 |
| **运行时统计** | `api.get_runtime_stats()` 获取队列长度、处理耗时等 |

#### 💰 回测资金约束修复

| 更新项 | 说明 |
|-------|------|
| **资金校验** | 所有开仓按账户可用资金校验，资金不足自动裁剪手数 |
| **资金预占** | 待执行开仓单入队时预估资金占用，避免超额开仓 |
| **智能停止** | 资金耗尽且无持仓时提前终止回测 |
| **拒单可见** | 资金不足等关键信息在控制台显示（`log_important`） |

#### 🐛 BUG修复

| 更新项 | 说明 |
|-------|------|
| **CTP 线程阻塞** | tick 队列 + 独立处理线程，CTP 回调只入队立即返回 |
| **持仓查询翻倍** | `_on_position` 按 key 跟踪覆盖，不再累加 |
| **强平未处理** | 交易所强制平仓时本地持仓正确更新 |
| **终态订单残留** | 扩展终态判断，部分成交部分撤单的订单正确清理 |
| **实盘 is_ready** | 补齐 `RealTradingClient` 的 `is_ready()` 方法 |
| **断线认证重试** | 改用 `self.connected` 检查，断线后认证重试正确取消 |
| **WS 鉴权恢复** | data_server 重启后自动重新鉴权，不再无限重连失败 |
| **开盘假死** | data_server + Tick回调模式下智能节流，新K线立即触发 |

#### 📝 示例全面优化

| 更新项 | 说明 |
|-------|------|
| **注释重写** | 全部示例注释面向用户重写，去除内部术语 |
| **新增示例** | `B_自动换月示例.py`（自动移仓演示） |
| **移仓配置** | 所有 B 类策略统一添加自动移仓参数（默认关闭） |

详细更新内容请查看 [043.MD](043.MD)

### v0.4.2 (2026-02-22) 🚀 Linux支持 & 数据服务器重大升级

#### 📡 数据服务器升级

| 更新项 | 说明 |
|-------|------|
| **全新 data_server** | 独立数据服务器架构，更稳定更快速 |
| **订单流数据** | 新增12个订单流字段 |
| **实时K线推送** | WebSocket 毫秒级推送 |
| **历史K线补全** | 连接时自动预加载 |
| **多周期支持** | 服务端直接推送任意周期 |

#### 🐧 平台与功能

| 更新项 | 说明 |
|-------|------|
| **Linux 平台支持** | 新增 CTP Linux 二进制文件 (.so) |
| **精确时间请求** | start_time/end_time/limit 参数 |
| **断线重连优化** | 认证失败自动重试 |

详细更新内容请查看 [042.MD](042.MD)

### v0.4.1 (2026-02-04) 🐛 平今平昨Bug修复

| 更新项 | 说明 |
|-------|------|
| **昨仓识别修复** | `YdPosition` 改为 `Position - TodayPosition` |
| **解决问题** | 不再出现"错误50: 平今仓位不足" |

详细更新内容请查看 [更新日志_v0.4.1.md](更新日志_v0.4.1.md)

### v0.4.0 (2026-01) 🎯 合约参数自动获取

| 更新项 | 说明 |
|-------|------|
| **合约信息服务** | 自动获取合约参数，无需手动填写 |
| **账户查询** | 新增 `api.get_balance()` 等 |
| **数据库优化** | 线程安全写入 + 快速追加 |

详细更新内容请查看 [更新日志_v0.4.0.md](更新日志_v0.4.0.md)

### v0.3.9 (2026-01) 🚀 重大升级

| 更新项 | 说明 |
|-------|------|
| **AI-Agent** | 新增 AI 量化策略编写助手 |
| **报告重制** | Plotly 交互式 HTML 报告，生成速度提升 5-10 倍 |
| **性能优化** | 数据窗口控制、内存占用降低 90%+ |

详细更新内容请查看 [更新日志_2026-01-06.md](更新日志_2026-01-06.md)

### v0.3.7 及更早

- 🔄 移除构建脚本和冗余文件
- ✅ 修复 CTP 登录报错乱码问题
- ✅ 完整的TICK流双驱动模式
- ✅ 多品种多周期支持
- ✅ 19个策略示例

---

---

**开始你的量化交易之旅！**

查看 [用户手册.md](https://github.com/songshuquant/ssquant/blob/main/%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C.md) 了解详细使用方法。
