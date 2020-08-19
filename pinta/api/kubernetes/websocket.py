import asyncio
from typing import List

import websockets
from aiohttp import ClientWebSocketResponse, WSMsgType
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.api_client import ApiClient
from kubernetes_asyncio.stream import WsApiClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from pinta.api.core.config import settings


async def tunnel1(ws: WebSocket, resp: ClientWebSocketResponse):
    while True:
        data = await ws.receive_bytes()
        await resp.send_bytes(data)


async def tunnel2(resp: ClientWebSocketResponse, ws: WebSocket):
    while True:
        data = await resp.receive_bytes()
        await ws.send_bytes(data)


async def exec_proxy(ws: WebSocket, pod: str, command: List[str], tty: bool, container: str = ""):
    if settings.K8S_DEBUG:
        await config.load_kube_config()
    else:
        await config.load_incluster_config()
    api = client.CoreV1Api(WsApiClient())
    resp = await api.connect_get_namespaced_pod_exec(pod,
                                                     "default",
                                                     command=command,
                                                     container=container,
                                                     stderr=True, stdin=True,
                                                     stdout=True, tty=tty,
                                                     _preload_content=False)
    t1 = asyncio.create_task(tunnel1(ws, resp))
    t2 = asyncio.create_task(tunnel2(resp, ws))
    try:
        await asyncio.gather(t1, t2)
    except TypeError:
        pass
    except WebSocketDisconnect:
        pass
    finally:
        await resp.close()


async def log_proxy(ws: WebSocket, pod: str, container: str = ""):
    if settings.K8S_DEBUG:
        await config.load_kube_config()
    else:
        await config.load_incluster_config()
    api = client.CoreV1Api(ApiClient())
    resp = await api.read_namespaced_pod_log(pod,
                                             "default",
                                             container=container,
                                             tail_lines=100,
                                             follow=True,
                                             _preload_content=False)
    try:
        while True:
            line = await resp.content.readline()
            if not line:
                break
            await ws.send_bytes(bytes([1]) + line)
    except websockets.exceptions.ConnectionClosedOK:
        pass
