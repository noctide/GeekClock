"""单实例锁。

使用 QLocalServer/QLocalSocket 实现跨进程互斥。
启动时：如果已有实例，向它发送"显示主窗口"的消息然后退出。
"""
import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

# 唯一标识符（避免和其他软件冲突）
SERVER_NAME = "GeekClock_SingleInstance_Lock_v1"


class SingleInstance(QObject):
    """单实例锁。

    使用方式：
        instance = SingleInstance()
        if instance.is_already_running():
            # 通知第一个实例显示窗口
            instance.notify_first_instance("show")
            sys.exit(0)
        # 否则继续启动
        instance.show_main_window_requested.connect(my_show_main)
    """

    show_main_window_requested = Signal()

    def __init__(self):
        super().__init__()
        self._server = None

    def is_already_running(self) -> bool:
        """检查是否已有实例在运行。"""
        # 尝试连接已存在的服务器
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(500):
            socket.disconnectFromServer()
            return True
        return False

    def notify_first_instance(self, message: str = "show") -> bool:
        """向已运行的实例发送消息（让它显示窗口）。"""
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if not socket.waitForConnected(500):
            return False
        socket.write(message.encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True

    def start_listening(self) -> bool:
        """启动监听服务器，接受后续实例的消息。"""
        # Linux 上服务器残留文件可能导致启动失败，先清理
        QLocalServer.removeServer(SERVER_NAME)

        self._server = QLocalServer()
        if not self._server.listen(SERVER_NAME):
            logger.error(f"监听失败：{self._server.errorString()}")
            return False

        self._server.newConnection.connect(self._on_new_connection)
        logger.info(f"单实例锁已启动：{SERVER_NAME}")
        return True

    def _on_new_connection(self) -> None:
        """有新实例尝试启动，处理消息。"""
        socket = self._server.nextPendingConnection()
        if not socket:
            return

        if socket.waitForReadyRead(500):
            data = socket.readAll().data().decode("utf-8", errors="ignore")
            logger.info(f"收到第二个实例的消息：{data}")
            if data == "show":
                self.show_main_window_requested.emit()

        socket.disconnectFromServer()

    def cleanup(self) -> None:
        """退出时调用，清理服务器。"""
        if self._server:
            self._server.close()
            QLocalServer.removeServer(SERVER_NAME)
