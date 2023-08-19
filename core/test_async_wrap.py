import asyncio
import time

import cyl_wrapper


# @cyl_wrapper.async_wrap
def print_task(i):
    print(f"start {i}")
    time.sleep(3)
    print(f"end {i}")

@cyl_wrapper.async_wrap
def hhhh(i):
    print_task(i)

async def do():
    tasks = []

    for i in range(10):
        task = hhhh(i)
        tasks.append(task)
    await asyncio.gather(*tasks)

## ========================================================
## ========================================================
if __name__ == '__main__':
    asyncio.run(do())



