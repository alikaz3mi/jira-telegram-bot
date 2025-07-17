"""Retry decorator for async functions with exponential backoff."""

import asyncio
import functools
from typing import Callable, Any, Tuple, Union

from jira_telegram_bot import LOGGER


def retry_async(
    exceptions: Tuple[type, ...] = (Exception,),
    tries: int = 3,
    backoff: float = 1.0,
    max_backoff: float = 60.0
) -> Callable:
    """Decorator for retrying async functions with exponential backoff.
    
    Args:
        exceptions: Tuple of exception types to catch and retry
        tries: Maximum number of attempts
        backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_backoff = backoff
            
            while attempt < tries:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    
                    if attempt >= tries:
                        LOGGER.error(f"Function {func.__name__} failed after {tries} attempts: {e}")
                        raise
                    
                    LOGGER.warning(
                        f"Function {func.__name__} failed on attempt {attempt}/{tries}: {e}. "
                        f"Retrying in {current_backoff} seconds..."
                    )
                    
                    await asyncio.sleep(current_backoff)
                    current_backoff = min(current_backoff * 2, max_backoff)
            
            return None  # Should never reach here
        
        return wrapper
    return decorator


def retry_sync(
    exceptions: Tuple[type, ...] = (Exception,),
    tries: int = 3,
    backoff: float = 1.0,
    max_backoff: float = 60.0
) -> Callable:
    """Decorator for retrying sync functions with exponential backoff.
    
    Args:
        exceptions: Tuple of exception types to catch and retry
        tries: Maximum number of attempts
        backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_backoff = backoff
            
            while attempt < tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    
                    if attempt >= tries:
                        LOGGER.error(f"Function {func.__name__} failed after {tries} attempts: {e}")
                        raise
                    
                    LOGGER.warning(
                        f"Function {func.__name__} failed on attempt {attempt}/{tries}: {e}. "
                        f"Retrying in {current_backoff} seconds..."
                    )
                    
                    import time
                    time.sleep(current_backoff)
                    current_backoff = min(current_backoff * 2, max_backoff)
            
            return None  # Should never reach here
        
        return wrapper
    return decorator
