import asyncio
import functools
import logging
import time
from collections.abc import (Awaitable, Callable, Collection, Coroutine,
                             Iterable, Mapping)
from functools import partial, wraps
from typing import (TYPE_CHECKING, Any, Generic, NamedTuple, Optional, Tuple,
                    TypeVar, Union, cast, overload)

import schedule

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

def callback(func: _CallableT) -> _CallableT:
    """Annotation to mark method as safe to call from within the event loop."""
    setattr(func, "_cyl_callback", True)
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return getattr(func, "_cyl_callback", False) is True


class Retry(object):
    def __init__(self, times: int=1, func_description: str="", time_sleep: float=0.1):
        self.times = times
        self.time_sleep = time_sleep
        self.func_description = func_description

    def __call__(self, func: Callable[..., Tuple[bool, Any]]):
        if not asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.func_description:
                    self.func_description = f"{func.__name__}()"
                ret, out = True, "did nothing..."
                for i in range(0, 1+self.times):
                    ret, out = func(*args, **kwargs)
                    if ret is True:
                        break
                    _LOGGER.warning(f"retry function {i}: {self.func_description}, out: {out}")
                    time.sleep(self.time_sleep)
                return (ret, out)
            return wrapper

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.func_description:
                self.func_description = f"{func.__name__}()"
            ret, out = True, "did nothing..."
            for i in range(0, 1+self.times):
                ret, out = await func(*args, **kwargs)
                if ret is True:
                    break
                _LOGGER.warning(f"retry function {i}: {self.func_description}, out: {out}")
                await asyncio.sleep(self.time_sleep)
            return (ret, out)
        return wrapper


class RetryUntil(object):
    def __init__(self, timeout: float=1, func_description: str="", time_sleep: float=0.1):

        self.timeout = timeout
        self.time_sleep = time_sleep
        self.func_description = func_description

    def __call__(self, func: Callable[..., Tuple[bool, Any]]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.func_description:
                self.func_description = f"{func.__name__}()"
            ret, out = True, "did nothing..."
            counter = 0
            start_time = time.time()
            while (time.time() - start_time < self.timeout):
                ret, out = func(*args, **kwargs)
                if ret is True:
                    break
                _LOGGER.warning(f"retry function {counter}: {self.func_description}, out: {out}")
                counter += 1
                time.sleep(self.time_sleep)
            return (ret, out)
        return wrapper


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run

def handle_exception(func):
    if not asyncio.iscoroutinefunction(func):
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = f"Exception caught- {type(e).__name__}: {e}"
                return False, msg
                # print(f"Exception caught: {e}")
                # traceback.print_exc()
        return inner

    async def async_inner(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            msg = f"Exception caught- {type(e).__name__}: {e}"
            return False, msg
            # print(f"Exception caught: {e}")
            # traceback.print_exc()
    return async_inner


def run_time(f):
    if not asyncio.iscoroutinefunction(f):
        @wraps(f)
        def core(*args, **kwargs):
            start_time = time.time()
            ret = f(*args, **kwargs)
            end_time = time.time()
            msecs_time = (end_time - start_time) * 1000
            print(f"{f.__name__}() spent time: {msecs_time} ms")
            return ret
        return core
    
    @wraps(f)
    async def async_core(*args, **kwargs):
        start_time = time.time()
        ret = await f(*args, **kwargs)
        end_time = time.time()
        msecs_time = (end_time - start_time) * 1000
        print(f"{f.__name__}() spent time: {msecs_time} ms")
        return ret
    return async_core


def schedule_do(interval: int=1, units: str="seconds"):
    def decorator(func):
        @wraps(func)
        def do(*args, **kwargs):
            pfunc = partial(func, *args, **kwargs)
            job = schedule.every(interval)
            return getattr(job, units).do(pfunc)
        return do
    
    return decorator
    

def setVar(varname: str, val: object):
    def wrapper(originFunction):
        @wraps(originFunction)
        def inner(*arg, **kwarg):
            return originFunction(*arg, **kwarg)
        setattr(inner, varname, val)
        return inner  # wrapper return
    return wrapper