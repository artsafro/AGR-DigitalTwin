"""Execute a file through the existing local Blender MCP addon."""
import json
import socket
import sys
from pathlib import Path

code = Path(sys.argv[1]).read_text(encoding='utf-8-sig')
with socket.create_connection(('127.0.0.1', 9876), 5) as sock:
    sock.settimeout(120)
    sock.sendall(json.dumps({'type': 'execute_code', 'params': {'code': code}}).encode())
    data = b''
    while True:
        part = sock.recv(65536)
        if not part:
            raise RuntimeError('Connection closed before JSON response')
        data += part
        try:
            result = json.loads(data)
            break
        except (ValueError, UnicodeDecodeError):
            continue
if result.get('status') != 'success':
    raise RuntimeError(result)
print(result['result'].get('result', result['result']))
