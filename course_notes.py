## https://zestedesavoir.com/articles/1568/decouvrons-la-programmation-asynchrone-en-python

## I - Coroutines 

def tic_tac():
  print("Tic")
  yield # The function decides to stop its execution with that instruction.
  print("Tac")
  yield
  return "Boum!"

# The simple fact that the function uses the yield keyword is enough to define a COROUTINE. 

task = tic_tac() # Doesn't run the function at all (not even "Tic") : generates a task.
print(task) # "generator object"

# The task can be run with the next() function a bit like an iterator : 
while True:
  try:
    next(task)
  except StopIteration as stop:
    print("Return value:", repr(stop.value))
    break

## II - Task : Simple abstraction over that iteration model :
STATUS_NEW = 'NEW'
STATUS_RUNNING = 'RUNNING'
STATUS_FINISHED = 'FINISHED'
STATUS_ERROR = 'ERROR'

class Task:
  def __init__(self, coro):
    self.coro = coro  # Coroutine à exécuter
    self.name = coro.__name__
    self.status = STATUS_NEW  # Statut de la tâche
    self.return_value = None  # Valeur de retour de la coroutine
    self.error_value = None  # Exception levée par la coroutine

  # Exécute la tâche jusqu'à la prochaine pause
  def run(self):
    try:
      # On passe la tâche à l'état RUNNING et on l'exécute jusqu'à
      # la prochaine suspension de la coroutine.
      self.status = STATUS_RUNNING
      next(self.coro)
    except StopIteration as err:
      # Si la coroutine se termine, la tâche passe à l'état FINISHED
      # et on récupère sa valeur de retour.
      self.status = STATUS_FINISHED
      self.return_value = err.value
    except Exception as err:
      # Si une autre exception est levée durant l'exécution de la
      # coroutine, la tâche passe à l'état ERROR, et on récupère
      # l'exception pour laisser l'utilisateur la traiter.
      self.status = STATUS_ERROR
      self.error_value = err

  def is_done(self):
    return self.status in {STATUS_FINISHED, STATUS_ERROR}

  def __repr__(self):
    result = ''
    if self.is_done():
      result = " ({!r})".format(self.return_value or self.error_value)

    return "<Task '{}' [{}]{}>".format(self.name, self.status, result)
  
task = Task(tic_tac())
while not task.is_done():
  task.run()
  print(task)

## III - Event loops
# The whole point of concurrent/async programming is to "do something else" while a 
# task is waiting for an event. Let's write a task queue :

from collections import deque
running_tasks = deque()
running_tasks.append(Task(tic_tac()))
running_tasks.append(Task(tic_tac()))

# Event loop prototype
while running_tasks: 
  # Get the "first in" task and run it
  task = running_tasks.popleft()
  task.run()
  if task.is_done():
    # If task is terminated we print it
    print(task)
  else:
    # If not done we replace the task at the right of the fifo queue
    running_tasks.append(task)

class Loop:
  def __init__(self):
    self._running = deque()

  def _loop(self):
    task = self._running.popleft()
    task.run()
    if task.is_done():
      print(task)
      return
    self.schedule(task)

  def run_until_empty(self):
    while self._running:
      self._loop()

  def run_until_complete(self, task):
    task = self.schedule(task)
    while not task.is_done():
      self._loop()

  def schedule(self, task):
    if not isinstance(task, Task):
      task = Task(task)
    self._running.append(task)
    return task
  
def spam():
  print("Spam")
  yield
  print("Eggs")
  yield
  print("Bacon")
  yield
  return "SPAM!"

event_loop = Loop()
event_loop.schedule(tic_tac())
event_loop.schedule(spam())
event_loop.run_until_empty()

# In "real cases" we won't call yield ourselves but some kind of system call capable 
# to interrupt themselves while saying to the kernel "call me back when you have something new".
# (poll, select, etc on UNIX)

## IV - Coroutines call

# Run a task sequentially from a coroutine :
def example():
  print("Tâche 'example'")
  print("Lancement de la tâche 'subtask'")
  yield from subtask()
  print("Retour dans 'example'")
  for _ in range(3):
    print("(example)")
    yield

def subtask():
  print("Tâche 'subtask'")
  for _ in range(2):
    print("(subtask)")
    yield

event_loop = Loop() # Or loop = asyncio.get_event_loop() ... :)
event_loop.run_until_complete(example())

# Schedule a task on the main loop (run it concurrently) - from a coroutine
# Use asyncio ensure_future(subtask())
# In our primitive model it is equivalent to doing loop.schedule(coro)
# NB: We have no control over the life of the subtask, it can end long after our calling task.
# So if we do run_until_complete of the main task, subtask may not have finished at the end. 
# We'll have to call run_until_empty to clean up.

## V - Cancel a task
