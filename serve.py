# serve.py - Production server with Waitress + mDNS + logging
from waitress import serve
from app import app, logger, setup_logging
import socket
import logging
import os         
from zeroconf import ServiceInfo, Zeroconf

logging.getLogger('waitress').setLevel(logging.INFO)


def register_mdns_service(port=8081):
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    info = ServiceInfo(
        "_http._tcp.local.",
        "Transferencia a Bolivia._http._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={'path': '/'},
        server="transferencia.local.",
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    logger.info(f"mDNS registered: transferencia.local:{port} -> {local_ip}")
    return zeroconf, info


if __name__ == '__main__':
    setup_logging(app)
    zeroconf, service_info = None, None
    port = 8081

    try:
        zeroconf, service_info = register_mdns_service(port=port)

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        logger.info("=" * 60)
        logger.info("PRODUCTION MODE (Waitress)")
        logger.info(f"Local:   http://localhost:{port}")
        logger.info(f"Network: http://{local_ip}:{port}")
        logger.info(f"Friendly: http://transferencia.local:{port}")
        logger.info("=" * 60)

        serve(app, host='0.0.0.0', port=port, threads=6)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        raise
    finally:
        if zeroconf and service_info:
            try:
                zeroconf.unregister_service(service_info)
                zeroconf.close()
            except Exception as e:
                logger.warning(f"mDNS unregister error: {e}")