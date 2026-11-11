import time
import functools
from typing import Callable, Any, Type, Tuple
from src.utils.logger import logger
from src.config import Config

def retry_api_call(
    max_retries: int = None,
    backoff_factor: float = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    action_name: str = "API_CALL",
    on_exhausted_callback: Callable[[str, Exception], None] = None
):
    """
    Decorator for retrying API calls with exponential backoff.
    
    :param max_retries: Maximum number of retry attempts. Defaults to Config.MAX_RETRIES.
    :param backoff_factor: Multiplier for exponential backoff. Defaults to Config.RETRY_BACKOFF_FACTOR.
    :param exceptions: Tuple of exception types to catch and retry.
    :param action_name: Name of the action for logging and auditing.
    :param on_exhausted_callback: Optional hook called when all retries fail.
    """
    if max_retries is None:
        max_retries = Config.MAX_RETRIES
    if backoff_factor is None:
        backoff_factor = Config.RETRY_BACKOFF_FACTOR

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            wait_time = 1.0

            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            f"[{action_name}] All {max_retries} retry attempts failed for {func.__name__}. Error: {e}"
                        )
                        if on_exhausted_callback:
                            try:
                                on_exhausted_callback(action_name, e)
                            except Exception as cb_err:
                                logger.warning(f"Error in retry exhausted callback: {cb_err}")
                        raise e

                    logger.warning(
                        f"[{action_name}] Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    wait_time *= backoff_factor

        return wrapper
    return decorator
