"""
本地复权模块 — 对从 data_server 获取的原始(raw)数据进行本地复权

设计思路:
    data_server（远程服务器）只存储不复权(raw)数据，
    复权计算在 ssquant 框架本地完成。

当前状态:
    占位实现 — 直通原始数据（等效于不复权）。
    后续实现后复权算法后，只需修改本文件即可，上层调用无需改动。

使用方式:
    from ssquant.data.local_adjust import apply_local_adjust
    df_adjusted = apply_local_adjust(df_raw, symbol, period, adjust_type)

未来 TODO:
    1. 实现后复权(hfq)算法：根据主力合约换月日期和价差计算复权因子
    2. 实现前复权(qfq)算法
    3. 缓存复权因子，避免重复计算
"""

import pandas as pd


def apply_local_adjust(df: pd.DataFrame, symbol: str, period: str,
                       adjust_type: str) -> pd.DataFrame:
    """
    对原始K线数据进行本地复权
    
    Args:
        df: 原始K线DataFrame（必须包含 open/high/low/close 列）
        symbol: 合约代码，如 'y888', 'rb888'
        period: K线周期，如 '1M', '1D'
        adjust_type: 复权类型
            '0' — 不复权（直接返回原始数据）
            '1' — 后复权
            '2' — 前复权
    
    Returns:
        复权后的DataFrame（与输入格式完全一致）
        当前为占位实现，直接返回原始数据
    """
    if df is None or df.empty:
        return df
    
    # 不复权：直接返回
    if adjust_type == '0':
        return df
    
    # ========== 占位：后续在此处实现复权算法 ==========
    #
    # 后复权(adjust_type='1')算法思路:
    #   1. 获取主力合约换月日期表（何时从旧主力切到新主力）
    #   2. 在每个换月点计算价差 = 新合约价 - 旧合约价
    #   3. 将换月点之前的所有价格加上累计价差
    #   4. 价格列: open, high, low, close 都需要调整
    #
    # 前复权(adjust_type='2')算法思路:
    #   类似后复权，但调整方向相反（调整换月点之后的数据）
    #
    # 示例（伪代码）:
    #   factors = get_adjust_factors(symbol)  # 获取复权因子
    #   for date, delta in factors:
    #       mask = df.index < date
    #       df.loc[mask, ['open','high','low','close']] += delta
    #
    # ================================================================

    # 当前：不做任何调整，等同于不复权
    # 上层已通过 ENABLE_REMOTE_ADJUST=False 强制 adjust_type='0'，
    # 此处作为双重保险和未来扩展入口
    return df
