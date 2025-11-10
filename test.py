
import threading
time = 5  # seconds
ent = threading.Event()
ent.wait(timeout = time)
