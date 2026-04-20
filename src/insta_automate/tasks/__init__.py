from prefect import task


def ia_task(retries: int = 3, retry_delay_seconds: float = 30):
    return task(retries=retries, retry_delay_seconds=retry_delay_seconds)
