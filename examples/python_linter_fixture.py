# ruff: noqa: F821
def process_order(order):
    try:
        save_order(order)
    except Exception:
        logger.error("failed to save order")
        send_notification(order)


def safe_order(order):
    try:
        save_order(order)
    except ValueError:
        raise
