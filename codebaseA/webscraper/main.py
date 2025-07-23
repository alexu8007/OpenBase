import snakeCatcher
import msgpack
from typing import List, Set, Tuple

# Module-level variables to hold the persistent state of the data collection.
# These will be loaded from files at the start and saved periodically.
_all_game_data: List[dict] = []
_processed_snakes_cache: Set[str] = set()
_processed_games_cache: Set[str] = set()

# Configuration constant for the data collection process.
_SNAKE_LEADERBOARD_CUTOFF: float = 0.10 # Only get data on the top N percent of the snakes

def _load_persistent_data() -> Tuple[List[dict], Set[str], Set[str]]:
    """
    Loads previously saved game data, processed snake IDs, and processed game IDs
    from msgpack files. This function attempts to load from the 'data/' directory.

    Returns:
        A tuple containing:
        - all_game_data (List[dict]): A list of dictionaries, where each dictionary
          represents data for a processed game.
        - processed_snakes_cache (Set[str]): A set of snake IDs that have already
          been processed.
        - processed_games_cache (Set[str]): A set of game IDs that have already
          been processed.
    """
    all_game_data: List[dict] = []
    processed_snakes_cache: Set[str] = set()
    processed_games_cache: Set[str] = set()

    try:
        with open('data/used_games.msgpack', 'rb') as f:
            processed_games_cache = set(msgpack.loads(f.read()))
        print(f"Loaded {len(processed_games_cache)} existing processed game IDs.")
    except FileNotFoundError:
        print("No existing 'data/used_games.msgpack' found. Starting with an empty game cache.")
    except Exception as e:
        print(f"Error loading 'data/used_games.msgpack': {e}. Starting with an empty game cache.")

    try:
        with open('data/used_snakes.msgpack', 'rb') as f:
            processed_snakes_cache = set(msgpack.loads(f.read()))
        print(f"Loaded {len(processed_snakes_cache)} existing processed snake IDs.")
    except FileNotFoundError:
        print("No existing 'data/used_snakes.msgpack' found. Starting with an empty snake cache.")
    except Exception as e:
        print(f"Error loading 'data/used_snakes.msgpack': {e}. Starting with an empty snake cache.")

    try:
        with open('data/data.msgpack', 'rb') as f:
            all_game_data = msgpack.loads(f.read())
        print(f"Loaded {len(all_game_data)} existing game records.")
    except FileNotFoundError:
        print("No existing 'data/data.msgpack' found. Starting with an empty data list.")
    except Exception as e:
        print(f"Error loading 'data/data.msgpack': {e}. Starting with an empty data list.")

    return all_game_data, processed_snakes_cache, processed_games_cache

def _save_persistent_data(
    all_game_data: List[dict],
    processed_games_cache: Set[str],
    processed_snakes_cache: Set[str]
) -> None:
    """
    Saves the current state of game data, processed game IDs, and processed snake IDs
    to msgpack files in the 'newdata/' directory.

    Args:
        all_game_data (List[dict]): The list of all collected game data.
        processed_games_cache (Set[str]): The set of game IDs that have been processed.
        processed_snakes_cache (Set[str]): The set of snake IDs that have been processed.
    """
    try:
        with open('newdata/used_games.msgpack', 'wb') as f:
            f.write(msgpack.dumps(list(processed_games_cache)))
        with open('newdata/used_snakes.msgpack', 'wb') as f:
            f.write(msgpack.dumps(list(processed_snakes_cache)))
        with open('newdata/data.msgpack', 'wb') as f:
            f.write(msgpack.dumps(all_game_data))
    except Exception as e:
        print(f"Error saving data: {e}")

def _process_single_game(
    game_id: str,
    all_game_data: List[dict],
    processed_games_cache: Set[str],
    game_index: int
) -> bool:
    """
    Processes a single game by fetching its data and adding it to the main data list
    if it hasn't been processed before.

    Args:
        game_id (str): The ID of the game to process.
        all_game_data (List[dict]): The list where collected game data will be appended.
        processed_games_cache (Set[str]): A set to keep track of processed game IDs.
        game_index (int): The 0-based index of the current game being processed within
                          the snake's recent games (for logging).

    Returns:
        bool: True if the game was successfully processed and added, False otherwise.
    """
    if game_id in processed_games_cache:
        print(''.join(['\t\tGame ', str(game_index), ' with id ', game_id, ' skipped as it already exists in the database.']))
        return False

    print(f"\t\tProcessing game {game_index} with id {game_id}")
    game_data = snakeCatcher.fetch_game_data(game_id)

    if game_data is False: # snakeCatcher.fetch_game_data returns False on error
        print(f"\t\tError processing game {game_index} with id {game_id}, skipped.")
        return False
    else:
        all_game_data.append(game_data)
        processed_games_cache.add(game_id)
        return True

def _process_single_snake(
    snake_id: str,
    all_game_data: List[dict],
    processed_snakes_cache: Set[str],
    processed_games_cache: Set[str],
    snake_index: int,
    total_snakes_to_process: int
) -> None:
    """
    Processes a single snake by fetching its recent games and processing each one.
    This function also handles adding the snake to the processed cache and
    periodically saving the collected data.

    Args:
        snake_id (str): The ID of the snake to process.
        all_game_data (List[dict]): The list where collected game data will be appended.
        processed_snakes_cache (Set[str]): A set to keep track of processed snake IDs.
        processed_games_cache (Set[str]): A set to keep track of processed game IDs.
        snake_index (int): The 1-based index of the current snake being processed
                           (for logging, e.g., "1/10").
        total_snakes_to_process (int): The total number of snakes targeted for processing.
    """
    if snake_id in processed_snakes_cache:
        print(f"\tSnake {snake_index}/{total_snakes_to_process} with id {snake_id} skipped as it already exists in the database.")
        return

    print(f"\tProcessing snake ({snake_index}/{total_snakes_to_process}) with id {snake_id}")
    games_processed_for_this_snake = 0
    recent_game_ids = snakeCatcher.fetch_snake_recent_games(snake_id)

    for game_idx, game_id in enumerate(recent_game_ids):
        if _process_single_game(game_id, all_game_data, processed_games_cache, game_idx):
            games_processed_for_this_snake += 1

    processed_snakes_cache.add(snake_id)
    print(f"\tCompleted snake {snake_index}. Processed {games_processed_for_this_snake} new games.")
    print(f"\tTotal data size: {len(all_game_data)} games.")
    _save_persistent_data(all_game_data, processed_games_cache, processed_snakes_cache)
    print("\tData saved to file.")

def main() -> None:
    """
    Main function to orchestrate the data collection process.
    It loads existing data, fetches new snake IDs from the leaderboard,
    applies a cutoff, processes each selected snake and its games,
    and saves the data periodically.
    """
    global _all_game_data, _processed_snakes_cache, _processed_games_cache

    # 1. Load existing data from previous sessions
    _all_game_data, _processed_snakes_cache, _processed_games_cache = _load_persistent_data()

    # 2. Fetch all snake IDs from the leaderboard
    all_leaderboard_snake_ids: List[str] = snakeCatcher.fetch_snakes_from_leaderboard()
    print(f"Found {len(all_leaderboard_snake_ids)} snakes on the leaderboard.")

    # 3. Apply the cutoff to select a subset of snakes for processing
    num_snakes_to_process = round(len(all_leaderboard_snake_ids) * _SNAKE_LEADERBOARD_CUTOFF)
    snake_ids_for_processing = all_leaderboard_snake_ids[:num_snakes_to_process]
    print(''.join(['Taking top ', str(len(snake_ids_for_processing)), ' snakes on the leaderboard for processing.']))

    # 4. Iterate through the selected snakes and process each one
    for i, snake_id in enumerate(snake_ids_for_processing):
        _process_single_snake(
            snake_id,
            _all_game_data,
            _processed_snakes_cache,
            _processed_games_cache,
            i + 1, # Use 1-based index for user-friendly display
            len(snake_ids_for_processing)
        )

if __name__ == "__main__":
    main()