import certifi
import ssl

from urllib.parse import urlencode, urlparse, urlunparse


def get_websocket_url(url):
    parsed_url = urlparse(url)
    parts = list(parsed_url)
    if parsed_url.scheme == 'http':
        parts[0] = 'ws'
    elif parsed_url.scheme == 'https':
        parts[0] = 'wss'
    return urlunparse(parts)


def websocket_call_args(configuration, *args, **kwargs):
    """An internal function to be called in api-client when a websocket
        connection is required. args and kwargs are the parameters of
        apiClient.request method."""

    url = args[1]
    headers = kwargs.get("headers")
    extra_headers = None
    if headers and 'authorization' in headers:
        extra_headers = {"authorization": headers['authorization']}

    # Expand command parameter list to individual command params
    query_params = []
    for key, value in kwargs.get("query_params", {}):
        if key == 'command' and isinstance(value, list):
            for command in value:
                query_params.append((key, command))
        else:
            query_params.append((key, value))

    if query_params:
        url += '?' + urlencode(query_params)

    websocket_url = get_websocket_url(url)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if websocket_url.startswith('wss://') and configuration.verify_ssl:
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.load_verify_locations(cafile=configuration.ssl_ca_cert or certifi.where())
        if configuration.assert_hostname is not None:
            ssl_context.check_hostname = configuration.assert_hostname
    else:
        ssl_context.verify_mode = ssl.CERT_NONE

    if configuration.cert_file and configuration.key_file:
        ssl_context.load_cert_chain(certfile=configuration.cert_file, keyfile=configuration.key_file)
    return dict(uri=websocket_url, ssl=ssl_context, subprotocols=['v4.channel.k8s.io'], extra_headers=extra_headers)


def stream(func, *args, **kwargs):
    """Stream given API call using websocket.
    Extra kwarg: capture-all=True - captures all stdout+stderr for use with WSClient.read_all()"""

    def _intercept_request_call(*args, **kwargs):
        # old generated code's api client has config. new ones has
        # configuration
        try:
            config = func.__self__.api_client.configuration
        except AttributeError:
            config = func.__self__.api_client.config

        return websocket_call_args(config, *args, **kwargs)

    prev_request = func.__self__.api_client.request
    try:
        func.__self__.api_client.request = _intercept_request_call
        return func(*args, **kwargs)
    finally:
        func.__self__.api_client.request = prev_request
