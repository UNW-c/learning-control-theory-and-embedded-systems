import logging


def setup_logging(level: int = logging.INFO) -> None:
    """统一日志格式，禁止使用裸打印调试。"""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )