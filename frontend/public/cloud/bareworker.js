!function() {
    "use strict";

    const nativePostMessage = MessagePort.prototype.postMessage;
    let transport = null;
    let transportName = "";
    let streamTransferSupported = null;

    function reportError(port, error) {
        nativePostMessage.call(port, {
            type: "error",
            error: error instanceof Error ? error.message : error
        });
    }

    function checkStreamTransfer() {
        if (streamTransferSupported !== null) return streamTransferSupported;
        const { port1 } = new MessageChannel();
        const stream = new ReadableStream();
        try {
            nativePostMessage.call(port1, stream, [stream]);
            streamTransferSupported = true;
        } catch (e) {
            streamTransferSupported = false;
        }
        return streamTransferSupported;
    }

    async function handleFetch(msg, port, clientTransport) {
        const response = await clientTransport.request(
            new URL(msg.fetch.remote),
            msg.fetch.method,
            msg.fetch.body,
            msg.fetch.headers,
            null
        );

        if (!checkStreamTransfer() && response.body instanceof ReadableStream) {
            const resp = new Response(response.body);
            response.body = await resp.arrayBuffer();
        }

        const transferables = [];
        if (response.body instanceof ReadableStream || response.body instanceof ArrayBuffer) {
            transferables.push(response.body);
        }

        nativePostMessage.call(port, {
            type: "fetch",
            fetch: response
        }, transferables);
    }

    function proxyToRemote(msg, port) {
        const transferables = [port];
        if (msg.fetch?.body) transferables.push(msg.fetch.body);
        if (msg.websocket?.channel) transferables.push(msg.websocket.channel);
        
        nativePostMessage.call(transport, {
            message: msg,
            port: port
        }, transferables);
    }

    function setupPort(port) {
        port.onmessage = async (event) => {
            const { port: clientPort, message: msg } = event.data;

            try {
                switch (msg.type) {
                    case "ping":
                        nativePostMessage.call(clientPort, { type: "pong" });
                        break;
                    case "get":
                        clientPort.postMessage({ type: "get", name: transportName });
                        break;
                    case "set":
                        const AsyncFunction = (async function() {}).constructor;
                        if (msg.client.function === "bare-mux-remote") {
                            transport = msg.client.args[0];
                            transportName = `bare-mux-remote (${msg.client.args[1]})`;
                        } else {
                            const loader = new AsyncFunction(msg.client.function);
                            const [TransportClass, name] = await loader();
                            transport = new TransportClass(...msg.client.args);
                            transportName = name;
                        }
                        nativePostMessage.call(clientPort, { type: "set" });
                        break;
                    case "fetch":
                        if (!transport) throw new Error("No Bare transport set.");
                        if (transport instanceof MessagePort) return proxyToRemote(msg, clientPort);
                        if (!transport.ready) await transport.init();
                        await handleFetch(msg, clientPort, transport);
                        break;
                    case "websocket":
                        if (!transport) throw new Error("No Bare transport set.");
                        if (transport instanceof MessagePort) return proxyToRemote(msg, clientPort);
                        if (!transport.ready) await transport.init();
                        handleWebSocket(msg, clientPort, transport);
                        break;
                }
            } catch (err) {
                reportError(clientPort, err);
            }
        };
    }

    function handleWebSocket(msg, clientPort, clientTransport) {
        const [send, close] = clientTransport.connect(
            new URL(msg.websocket.url),
            msg.websocket.protocols,
            msg.websocket.requestHeaders,
            (onOpen) => {
                nativePostMessage.call(msg.websocket.channel, { type: "open", args: [onOpen] });
            },
            (onMsg) => {
                const transfer = onMsg instanceof ArrayBuffer ? [onMsg] : [];
                nativePostMessage.call(msg.websocket.channel, { type: "message", args: [onMsg] }, transfer);
            },
            (code, reason) => {
                nativePostMessage.call(msg.websocket.channel, { type: "close", args: [code, reason] });
            },
            (onErr) => {
                nativePostMessage.call(msg.websocket.channel, { type: "error", args: [onErr] });
            }
        );

        msg.websocket.channel.onmessage = (e) => {
            if (e.data.type === "data") send(e.data.data);
            else if (e.data.type === "close") close(e.data.closeCode, e.data.closeReason);
        };

        nativePostMessage.call(clientPort, { type: "websocket" });
    }

    new BroadcastChannel("flint-mux").postMessage({ type: "refreshPort" });
    self.onconnect = (e) => setupPort(e.ports[0]);
}();
