# SSQuant - 期货量化交易框架

<div align="center">

🐿️ **松鼠Quant** | 专业的期货CTP量化交易框架
<img width="728" height="352" alt="image" src="https://github.com/user-attachments/assets/26201b06-0992-44dd-8416-03edcbb8878b" />

[![PyPI](https://img.shields.io/pypi/v/ssquant.svg)](https://pypi.org/project/ssquant/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Non--Commercial-red.svg)](LICENSE)

[GitHub](https://github.com/songshuquant/ssquant) | [Gitee（国内推荐）](https://gitee.com/ssquant/ssquant)

**一次编写，三处运行** - 回测 / SIMNOW模拟 / 实盘CTP

</div>

---

## 🎯 核心特性

### ✅ 统一的策略框架

- **一套代码三处运行** - 同一份策略代码可在回测、SIMNOW模拟、实盘CTP三种环境下运行
- **完整的数据支持** - K线数据（1m/5m/15m/30m/1h/4h/1d）+ TICK逐笔数据
- **多品种多周期** - 同时交易多个品种，使用不同周期数据

### ✅ 强大的交易功能

- **自动开平仓管理** - 智能识别开平仓、今昨仓
- **智能算法交易** - 支持限价单排队、超时撤单、追价重发等高级逻辑
- **实时回调系统** - on_trade/on_order/on_cancel 实时通知
- **TICK流双驱动** - K线驱动 + TICK驱动两种模式

### ✅ 丰富的策略示例

- 19个完整策略示例
- 涵盖趋势、套利、轮动、期权、机器学习等类型
- 从入门到高级，循序渐进

---

## 🖥️ 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10+（⚠️ 目前仅支持 Windows，Linux 版本待更新） |
| **Python** | 3.9 ~ 3.14 |
| **CTP版本** | 6.7.7 ~ 6.7.10 |
| **内存** | 4GB+ |

---

## ⚡ 快速开始

### 1. 安装

从 GitHub/Gitee 源码安装

如果您下载了源码压缩包（通常解压后文件夹名为 `ssquant-main`），或者通过 git clone 拉取了代码：

1. 打开终端（CMD/PowerShell），进入该文件夹（确保能看到 `setup.py` 文件）。
2. 运行安装命令：

```bash
pip install -e .
```

> **注意**：
> - 命令最后有一个点 `.`，代表当前目录，不要漏掉。
> - 文件夹名字（如 `ssquant-main`）不影响安装，只要目录结构正确即可。

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
   ```

2. 如果没有找到，重新安装：
   ```bash
   
   # 从源码安装（在项目目录下执行）
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
# ========== 数据API认证 (松鼠俱乐部会员) ==========
API_USERNAME = "你的会员账号"
API_PASSWORD = "你的会员密码"
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

### 4. 切换模式只需改配置

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

所有示例在 `examples/` 目录（共19个）：

### 工具类 (A_开头)

| 文件 | 说明 |
|------|------|
| `A_工具_导入数据库DB示例.py` | 数据导入数据库 |
| `A_工具_数据库管理_查看与删除.py` | 数据库管理 |
| `A_撤单重发示例.py` | 订单撤单重发机制 |
| `A_穿透式测试脚本.py` | CTP穿透式认证测试 |

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

### 高级类 (C_开头)

| 文件 | 说明 |
|------|------|
| `C_期权交易策略.py` | 期权交易 |
| `C_期货期权组合策略.py` | 期货期权组合 |
| `C_纯Tick高频交易策略.py` | TICK流高频交易 |

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
│   │   └── trading_config.py   # 配置生成（账户配置在此）
│   ├── data/                   # 数据管理
│   │   ├── api_data_fetcher.py # API数据获取
│   │   └── local_data_loader.py # 本地数据加载
│   ├── ctp/                    # CTP二进制文件
│   │   ├── py39/ ~ py314/      # 各Python版本的CTP文件
│   │   └── loader.py           # CTP加载器
│   ├── pyctp/                  # CTP封装
│   │   ├── simnow_client.py    # SIMNOW客户端
│   │   └── real_trading_client.py  # 实盘客户端
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
- **系统**: Windows 10+（⚠️ 目前仅支持 Windows，Linux 版本待更新）
- **内存**: 4GB+
- **网络**: 稳定连接（实盘/SIMNOW）

### CTP版本支持

框架内置 CTP 6.7.7 ~ 6.7.10 版本，位于 `ssquant/ctp/pyXXX/` 目录：

| Python版本 | 目录 | 状态 |
|-----------|------|------|
| 3.9 | `py39/` | ✅ 已包含 |
| 3.10 | `py310/` | ✅ 已包含 |
| 3.11 | `py311/` | ✅ 已包含 |
| 3.12 | `py312/` | ✅ 已包含 |
| 3.13 | `py313/` | ✅ 已包含 |
| 3.14 | `py314/` | ✅ 已包含 |

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
