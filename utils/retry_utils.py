import time
import functools
from typing import Type, Tuple, Optional
from utils.logger import Logger

def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator to retry a function call upon exception.
    
    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each failure.
        exceptions: Tuple of exceptions to catch and retry on.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        Logger.error(f"Function {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise e
                    
                    Logger.warning(f"Attempt {attempt}/{max_attempts} for {func.__name__} failed: {e}. Retrying in {current_delay:.1f}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
