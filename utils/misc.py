from datetime import datetime


def time_limit(started_at: datetime, limit: float = 10) -> None:
    """Function that raises a exception if time difference between current time and started time exceed given limit.

    Args:
        started_at (datetime): start time.
        limit (float, optional): time limit in seconds. Defaults to 10.

    Raises:
        TimeoutError: Time limit exceeded.
    """
    current_time = datetime.now()
    if (current_time - started_at).seconds >= limit:
        raise TimeoutError("Time limit exceeded.")
    