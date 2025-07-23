from bs4 import BeautifulSoup as bs
import requests
import ws
from typing import List, Dict, Optional, Any

LEADERBOARD_URL = "https://play.battlesnake.com/leaderboard/standard"
SNAKE_RECENT_GAMES_URL = "https://play.battlesnake.com/api/leaderboardsnake/{snake_id}/recent-games/"
GAME_DATA_URL = "wss://engine.battlesnake.com/games/{game_id}/events"

# Define a default timeout for HTTP requests to prevent indefinite waits
REQUEST_TIMEOUT = 10  # seconds

def fetch_snakes_from_leaderboard() -> List[str]:
    """
    Fetches the IDs of all snakes currently listed on the Battlesnake standard leaderboard.

    This function sends an HTTP GET request to the LEADERBOARD_URL, parses the HTML
    response using BeautifulSoup, and extracts the 'data-snake-id' attribute from
    relevant HTML elements to compile a list of snake IDs.

    Returns:
        A list of strings, where each string is a unique snake ID found on the leaderboard.

    Raises:
        requests.exceptions.RequestException: If there's an issue connecting to the
                                              leaderboard URL or an HTTP error occurs.
    """
    leaderboard_response = requests.get(LEADERBOARD_URL, timeout=REQUEST_TIMEOUT)
    leaderboard_response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
    leaderboard_soup = bs(leaderboard_response.text, "html.parser")
    snake_elements = leaderboard_soup.find_all(attrs={"data-snake-id": True})
    snake_ids = (x.attrs["data-snake-id"] for x in snake_elements)
    return snake_ids

def fetch_snake_recent_games(snake_id: str) -> List[str]:
    """
    Fetches the IDs of recently played games for a specified snake.

    This function constructs a URL for the snake's recent games API endpoint,
    sends an HTTP GET request, and parses the JSON response to extract game IDs.

    Args:
        snake_id: The unique identifier (string) of the snake whose recent games are to be fetched.

    Returns:
        A list of strings, where each string is a game ID from the snake's recent games.
        Returns an empty list if no recent games are found or if the 'recentGames' key
        is missing from the API response.

    Raises:
        requests.exceptions.RequestException: If there's an issue connecting to the API
                                              or an HTTP error occurs.
        ValueError: If the API response is not valid JSON.
    """
    recent_games_url = SNAKE_RECENT_GAMES_URL.format(snake_id=snake_id)
    recent_games_response = requests.get(recent_games_url, timeout=REQUEST_TIMEOUT)
    recent_games_response.raise_for_status()  # Raise an exception for HTTP errors
    recent_games_data = recent_games_response.json()
    # Use .get() with a default empty list to safely handle missing 'recentGames' key
    recent_games_ids = (x["gameId"] for x in recent_games_data.get("recentGames", []))
    return recent_games_ids

def _process_game_turn_data(turn_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper function to process the 'Data' part of a single Battlesnake game turn event.

    Extracts information about alive snakes (ID and body segments) and food positions.
    Also identifies a winner if only one snake remains alive on the board.

    Args:
        turn_data: A dictionary representing the 'Data' field from a Battlesnake
                   websocket event, typically containing 'Snakes' and 'Food' lists.

    Returns:
        A dictionary containing:
        - 'snakes': A list of dictionaries, each representing an alive snake with 'id' and 'body'.
        - 'food': The list of food coordinates (as provided in the input `turn_data`).
        - 'winnerId': The ID (string) of the winning snake if only one is alive, otherwise None.
    """
    alive_snakes: List[Dict[str, Any]] = []
    for snake in turn_data.get("Snakes", []):
        # A snake is considered alive if its "Death" field is None
        if snake.get("Death") is None:
            alive_snakes.append({
                "id": snake.get("ID"),
                "body": snake.get("Body"),
            })

    winner_id: Optional[str] = None
    if len(alive_snakes) == 1:
        winner_id = alive_snakes[0]["id"]

    return {
        "snakes": alive_snakes,
        "food": turn_data.get("Food", []),
        "winnerId": winner_id
    }

def _read_websocket_response() -> Optional[Dict[str, Any]]:
    """
    Helper function to read the next response from the Battlesnake game websocket.

    This function wraps the `ws.read_ws_next_response()` call to handle its specific
    behavior of returning `False` on connection errors or if the game does not exist.

    Returns:
        The parsed JSON response as a dictionary if successful, or None if
        `ws.read_ws_next_response()` returns `False` (indicating an error or no data).
    """
    response = ws.read_ws_next_response()
    if response is False:  # Specific behavior of the 'ws' module
        return None
    return response

def fetch_game_data(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches detailed board information for each turn of a specified Battlesnake game
    via a websocket connection.

    This function establishes a websocket connection to the game, reads turn-by-turn
    data, processes it, and identifies the winner. It handles potential websocket
    connection errors and ensures the connection is properly closed.

    Args:
        game_id: The unique identifier (string) of the game to fetch data for.

    Returns:
        A dictionary containing:
        - 'states': A list of dictionaries, each representing a game turn's state
                    with 'snakes' and 'food' information.
        - 'winnerId': The ID (string) of the winning snake.
        Returns None if the game data cannot be fetched due to connection errors,
        the game being too short, or if no clear winner can be identified.
    """
    ws.create_ws_connection(game_id)
    states: List[Dict[str, Any]] = []
    winner_id: Optional[str] = None

    try:
        while True:
            response = _read_websocket_response()

            if response is None:
                # This indicates a websocket connection error or that the game doesn't exist.
                # The original logic discards short games with errors but keeps longer ones.
                if len(states) > 30:
                    print(f"Warning: Websocket connection error for game {game_id}, but enough states collected. Breaking loop.")
                    break  # Break if we have collected a substantial amount of data
                else:
                    print(f"Error: Websocket connection error for game {game_id} or game too short/non-existent. Excluding game.")
                    return None  # Exclude this game entirely

            # Check if the game has ended
            if response.get("Type") == "game_end":
                break

            # Process the current turn's data
            turn_info = _process_game_turn_data(response.get("Data", {}))
            states.append({
                "snakes": turn_info["snakes"],
                "food": turn_info["food"],
            })

            # Update the winner_id if a single snake remains alive in the current turn
            if turn_info["winnerId"] is not None:
                winner_id = turn_info["winnerId"]

    finally:
        # Ensure the websocket connection is closed regardless of how the loop exits
        ws.close_ws_connection()

    # Final validation: A game is considered valid only if a winner was identified
    if winner_id is None:
        print(f"Error: No clear winner identified for game {game_id}. Excluding game.")
        return None

    return {
        "states": states,
        "winnerId": winner_id
    }