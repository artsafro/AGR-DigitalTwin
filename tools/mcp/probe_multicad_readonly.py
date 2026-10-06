"""Verify project multiCAD connection continuity using inspection only."""
import asyncio
import json
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


def error_detail(exc):
    if isinstance(exc, BaseExceptionGroup):
        return '; '.join(error_detail(child) for child in exc.exceptions)
    return f'{type(exc).__name__}: {exc}'


async def main():
    config = tomllib.loads((ROOT / '.codex/config.toml').read_text(encoding='utf-8'))
    server = config['mcp_servers']['multiCAD']
    output = ROOT / 'tmp/mcp' / ('autocad-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir(parents=True, exist_ok=False)
    report = {'checks': [], 'passed': False, 'drawing_write_or_save_requested': False}
    params = StdioServerParameters(command=server['command'], args=server['args'],
                                   env={**os.environ, **server.get('env', {})})
    try:
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                report['tools'] = [t.name for t in (await session.list_tools()).tools]

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    value = (result.structuredContent or {}).get('result')
                    if value is None:
                        value = next(c.text for c in result.content if c.type == 'text')
                    data = json.loads(value) if isinstance(value, str) else value
                    report['checks'].append({'name': name, 'data': data})
                    if result.isError or data.get('success') is False or (
                            'total' in data and data['total'] != data['succeeded']):
                        raise RuntimeError(str(data))
                    return data

                running = await call('manage_session', {'operations': '[{"action":"check_running"}]'})
                if running['results'][0].get('running_cad_types') != ['autocad']:
                    raise RuntimeError('Expected only the already-running AutoCAD; no launch requested')
                await call('manage_session', {'operations': '[{"action":"connect"},{"action":"status"}]'})
                before = await call('export_data', {'format': 'json', 'scope': 'all'})
                for _ in range(4):
                    status = await call('manage_session', {'operations': '[{"action":"status"}]'})
                    if status['results'][0]['status'].get('autocad') != 'connected':
                        raise RuntimeError('Connection continuity lost')
                    await call('manage_files', {'operations': 'list'})
                    await call('manage_layers', {'operations': 'list'})
                    await call('manage_blocks', {'operations': 'list'})
                await asyncio.gather(
                    call('manage_files', {'operations': 'list'}),
                    call('manage_layers', {'operations': 'list'}))
                after = await call('export_data', {'format': 'json', 'scope': 'all'})
                report['readback_unchanged'] = before == after
                if not report['readback_unchanged']:
                    raise RuntimeError('Entity data changed during inspection')
                report['passed'] = True
    except Exception as exc:
        report['error'] = error_detail(exc)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'calls': len(report['checks']),
                      'output': str(output), 'error': report.get('error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
