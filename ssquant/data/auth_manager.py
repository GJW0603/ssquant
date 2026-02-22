"""
鉴权管理器 — 通过 data_server 代理验证用户身份

工作流程：
1. 首次调用 verify_auth() 时，将账号密码发送给 data_server 的鉴权接口
2. data_server 内部转发至 kanpan789.com 完成实际验证（鉴权核心逻辑不在开源框架中）
3. 验证成功后缓存结果（整个运行周期内只验证一次）
"""

import requests
import threading

# ========== 模块级缓存（进程内单例） ==========
_auth_lock = threading.Lock()
_auth_result = None   # None=未检查, True=通过, False=失败
_auth_message = ""


def _get_auth_url() -> str:
    """获取 data_server 鉴权接口地址"""
    try:
        from ..config._server_config import DATA_SERVER
        api_url = DATA_SERVER.get('api_url', 'http://121.237.178.245:8086')
        return f"{api_url.rstrip('/')}/api/auth/verify"
    except Exception:
        return 'http://121.237.178.245:8086/api/auth/verify'


def verify_auth(username: str = None, password: str = None) -> bool:
    """
    验证用户身份（仅首次调用时真正请求 data_server，后续使用缓存）
    
    鉴权流程: ssquant → data_server → kanpan789.com
    
    Args:
        username: API账号，为 None 时自动从 trading_config 读取
        password: API密码
    
    Returns:
        True=鉴权成功, False=鉴权失败
    """
    global _auth_result, _auth_message
    
    with _auth_lock:
        if _auth_result is not None:
            return _auth_result
        
        if username is None or password is None:
            try:
                from ..config.trading_config import get_api_auth
                username, password = get_api_auth()
            except Exception:
                _auth_result = False
                _auth_message = "未配置API账号"
                return False
        
        if not username or not password:
            _auth_result = False
            _auth_message = "API账号或密码为空"
            _print_fail()
            return False
        
        auth_url = _get_auth_url()
        print(f"\n[鉴权] 正在验证账号 {username} ...")
        
        try:
            response = requests.get(
                auth_url,
                params={'username': username, 'password': password},
                timeout=(5, 10),
            )
            
            data = response.json()
            
            if data.get('authenticated'):
                _auth_result = True
                _auth_message = data.get('message', '鉴权成功')
                print(f"[鉴权] 验证通过\n")
            else:
                _auth_message = data.get('message', f'鉴权失败 (HTTP {response.status_code})')
                
        except requests.Timeout:
            _auth_message = "连接超时 (data_server 无响应)"
        except requests.ConnectionError:
            _auth_message = "无法连接 data_server，请确认服务已启动"
        except Exception as e:
            _auth_message = f"异常: {e}"
        
        if _auth_result is None:
            _auth_result = False
            _print_fail()
        
        return _auth_result


def is_authenticated() -> bool:
    """检查是否已鉴权通过（如果未检查过，自动触发验证）"""
    if _auth_result is None:
        return verify_auth()
    return _auth_result


def get_auth_message() -> str:
    """获取鉴权结果消息"""
    return _auth_message


def reset_auth():
    """重置鉴权状态（用于重新验证）"""
    global _auth_result, _auth_message
    with _auth_lock:
        _auth_result = None
        _auth_message = ""


def _print_fail():
    """打印鉴权失败信息"""
    print(f"[鉴权] 验证失败: {_auth_message}")
    print(f"[鉴权] 请检查 ssquant/config/trading_config.py 中的 API_USERNAME 和 API_PASSWORD")
    print(f"[鉴权] 如有疑问，请联系小松鼠 微信: viquant01\n")
