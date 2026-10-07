import time


time.sleep(2)
raise RuntimeError('delayed startup failure')
