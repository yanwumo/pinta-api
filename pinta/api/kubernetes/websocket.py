import asyncio
from typing import List, Optional

import websockets
from kubernetes import config, client
from starlette.websockets import WebSocket, WebSocketDisconnect

from pinta.api.kubernetes.exec_client import stream
from pinta.api.core.config import settings


async def tunnel1(ws: WebSocket, resp: websockets.WebSocketClientProtocol):
    while True:
        data = await ws.receive_bytes()
        await resp.send(data)


async def tunnel2(resp: websockets.WebSocketClientProtocol, ws: WebSocket):
    while True:
        data = await resp.recv()
        await ws.send_bytes(data)


async def proxy(ws: WebSocket, pod: str, command: List[str], container: Optional[str] = None):
    if settings.K8S_DEBUG:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    api = client.CoreV1Api()
    call_args = stream(api.connect_get_namespaced_pod_exec,
                       name=pod,
                       namespace="default",
                       command=command,
                       container=container,
                       stderr=True, stdin=True,
                       stdout=True, tty=True,
                       _preload_content=False)
    async with websockets.connect(**call_args) as resp:
        t1 = asyncio.create_task(tunnel1(ws, resp))
        t2 = asyncio.create_task(tunnel2(resp, ws))
        try:
            await asyncio.gather(t1, t2)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except WebSocketDisconnect:
            pass
