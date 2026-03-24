"""TCP socket server for receiving SBPL print data."""

import socket
import threading
import logging
from typing import Callable, Optional
from datetime import datetime

from src.config.settings import NetworkConfig

logger = logging.getLogger(__name__)


class PrinterTCPServer:
    """TCP server that listens for SBPL print data.

    Emulates a SATO printer's network interface on a configurable IP:port.
    """

    def __init__(self, config: NetworkConfig,
                 on_data_received: Optional[Callable[[bytes, str], None]] = None,
                 on_client_connected: Optional[Callable[[str], None]] = None,
                 on_client_disconnected: Optional[Callable[[str], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None):
        self.config = config
        self.on_data_received = on_data_received
        self.on_client_connected = on_client_connected
        self.on_client_disconnected = on_client_disconnected
        self.on_error = on_error

        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._client_threads: list = []

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        """Start the TCP server."""
        if self._running:
            return

        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.settimeout(1.0)
            self._server_socket.bind((self.config.ip, self.config.port))
            self._server_socket.listen(self.config.max_connections)
            self._running = True

            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()

            logger.info(f"Server started on {self.config.ip}:{self.config.port}")
        except OSError as e:
            error_msg = f"Failed to start server: {e}"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(error_msg)
            raise

    def stop(self):
        """Stop the TCP server."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("Server stopped")

    def _accept_loop(self):
        """Main accept loop - runs in background thread."""
        while self._running:
            try:
                client_socket, addr = self._server_socket.accept()
                client_addr = f"{addr[0]}:{addr[1]}"
                logger.info(f"Client connected: {client_addr}")

                if self.on_client_connected:
                    self.on_client_connected(client_addr)

                t = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_addr),
                    daemon=True,
                )
                self._client_threads.append(t)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("Accept error")
                break

    def _handle_client(self, client_socket: socket.socket, client_addr: str):
        """Handle data from a connected client."""
        buffer = bytearray()
        try:
            client_socket.settimeout(30.0)
            while self._running:
                try:
                    data = client_socket.recv(self.config.buffer_size)
                    if not data:
                        break
                    buffer.extend(data)

                    # Check for complete jobs (ETX byte or ESC+Z sequence)
                    while self._has_complete_job(buffer):
                        job_data, remaining = self._extract_job(buffer)
                        buffer = bytearray(remaining)
                        if job_data and self.on_data_received:
                            self.on_data_received(bytes(job_data), client_addr)
                except socket.timeout:
                    # If we have buffered data, process it
                    if buffer:
                        if self.on_data_received:
                            self.on_data_received(bytes(buffer), client_addr)
                        buffer.clear()
                    continue
        except (ConnectionError, OSError) as e:
            logger.info(f"Client {client_addr} disconnected: {e}")
        finally:
            # Process any remaining buffered data
            if buffer and self.on_data_received:
                self.on_data_received(bytes(buffer), client_addr)

            try:
                client_socket.close()
            except OSError:
                pass

            if self.on_client_disconnected:
                self.on_client_disconnected(client_addr)

    def _has_complete_job(self, data: bytearray) -> bool:
        """Check if buffer contains a complete print job."""
        # Look for ETX (0x03) or ESC+Z sequence
        if 0x03 in data:
            return True
        # Look for ESC + 'Z'
        for i in range(len(data) - 1):
            if data[i] == 0x1B and data[i + 1] == ord('Z'):
                return True
        return False

    def _extract_job(self, data: bytearray) -> tuple:
        """Extract the first complete job from the buffer.

        Returns (job_data, remaining_data).
        """
        # Try ETX first
        etx_pos = data.find(0x03)
        # Try ESC+Z
        esc_z_pos = -1
        for i in range(len(data) - 1):
            if data[i] == 0x1B and data[i + 1] == ord('Z'):
                esc_z_pos = i + 2
                break

        # Use whichever comes first
        end_pos = -1
        if etx_pos >= 0 and esc_z_pos >= 0:
            end_pos = min(etx_pos + 1, esc_z_pos)
        elif etx_pos >= 0:
            end_pos = etx_pos + 1
        elif esc_z_pos >= 0:
            end_pos = esc_z_pos

        if end_pos >= 0:
            return data[:end_pos], data[end_pos:]
        return data, bytearray()
