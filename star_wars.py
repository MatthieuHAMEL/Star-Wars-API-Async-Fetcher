import aiohttp
import asyncio
import urllib.parse
import datetime

MAX_PAGE=2

async def fetch_page(session, page_number):
  """Fetch JSON data for the given page_number from SWAPI starships endpoint. """
  url = f"https://swapi.dev/api/starships/?page={page_number}"
  print(f"fetching ... {url} at {datetime.datetime.now()}")
  async with session.get(url) as response:
      response.raise_for_status() # Maybe the page won't be valid ...
      return await response.json()

async def worker(session, queue: asyncio.Queue, starship_name: str, found_event: asyncio.Event, result_dict: dict):
  global MAX_PAGE
  """Continuously pulls a page number from the queue, fetches it,
  checks if the starship is in this page. If found, store the hyperdrive_rating
  and set the event so other workers can stop. If 'next' is absent, also set
  the event to signal no more pages."""
  while not found_event.is_set():
    try:
      page_number = await asyncio.wait_for(queue.get(), timeout=0.5)
    except asyncio.TimeoutError:
      # If we timeout waiting for pages, it might mean everything is done.
      return

    if page_number is None:
      # A sentinel to exit the loop.
      queue.task_done()
      return

    try:
      data = await fetch_page(session, page_number)
    except Exception as e:
      print(f"Error fetching page {page_number}: {e}")
      queue.task_done()
      continue

    # Check for our target starship
    for starship in data["results"]:
      if starship["name"].lower() == starship_name.lower():
        # Found it!
        result_dict["hyperdrive_rating"] = starship["hyperdrive_rating"]
        found_event.set()
        queue.task_done()
        return

    # If there's no next page, signal to all workers to stop
    if data["next"] is None:
      found_event.set()
      queue.task_done()
      return
    elif page_number == MAX_PAGE:
      # Parse the next page number from 'next' field
      parsed_url = urllib.parse.urlparse(data["next"])
      params = urllib.parse.parse_qs(parsed_url.query)
      next_page = int(params["page"][0])
      MAX_PAGE = MAX_PAGE + 1
      # Put the next page in the queue if we aren't done yet
      if not found_event.is_set():
        queue.put_nowait(next_page)
    queue.task_done()


async def find_starship_rating(starship_name: str, max_concurrency: int = 5) -> str:
  """
  Main entry: search for `starship_name` in SWAPI starships by
  paging through results. Run up to `max_concurrency` worker tasks in parallel.
  Returns the hyperdrive_rating if found, else None.
  """
  # This event will be set as soon as we find the starship or know there's no next page
  found_event = asyncio.Event()
  # Shared dictionary to store the final result
  result_dict = {}

  # Queue of page numbers to fetch : fill it with 1 to 5 as we know there'll be around 5 pages
  queue = asyncio.Queue()
  for i in range(0, MAX_PAGE+1): # There is no page 0 - this is to show that is has no incidence on the result
    queue.put_nowait(i)

  async with aiohttp.ClientSession() as session:
    # Launch worker tasks
    tasks = [
      asyncio.create_task(worker(session, queue, starship_name, found_event, result_dict))
      for _ in range(max_concurrency)
    ]

    # Wait for the queue to become empty or the event to be set.
    # If the starship is found or there's no next page, the event
    # will be set. In both cases we wait for all workers to finish.
    await queue.join()

    # Send a sentinel to each worker so it can terminate
    for _ in range(max_concurrency):
      queue.put_nowait(None)

    # Gather the tasks to ensure cleanup
    await asyncio.gather(*tasks, return_exceptions=True)
  return result_dict.get("hyperdrive_rating", None)


async def main():
  starship_to_find = "Jedi Interceptor" # For example
  rating = await find_starship_rating(starship_to_find, max_concurrency=5)
  if rating:
    print(f"Found '{starship_to_find}' with hyperdrive_rating = {rating}")
  else:
    print(f"Starship '{starship_to_find}' not found!")

if __name__ == "__main__":
  asyncio.run(main())
