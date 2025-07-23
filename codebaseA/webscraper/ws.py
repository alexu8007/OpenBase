
from websocket import create_connection
import json

# current websocket connection state and object
ws: dict = {"isInited": False, "connection": None}

# Stores the game ID for the current websocket connection
game_id_global: str | None = None

def create_ws_connection(game_id: str) -> bool:
    """
    Establishes a WebSocket connection to the Battlesnake game engine for a specific game.

    Args:
        game_id: The ID of the game to connect to.

    Returns:
        True if the connection was successfully established, False otherwise.
    """
    if ws["isInited"]:
        print("Attempted to create a websocket connection, but one is already connected.")
        return False
    global game_id_global
    game_id_global = game_id
    ws["connection"] = create_connection("wss://engine.battlesnake.com/games/{}/events".format(game_id))
    ws["isInited"] = True
    return True

def read_ws_next_response() -> dict | bool:
    """
    Reads the next JSON response from the established WebSocket connection.

    Returns:
        A dictionary containing the parsed JSON response if successful,
        or False if no connection is active or an error occurs during reading.
    """
    if not ws["isInited"]:
        print("Attempted to read data from websocket, but no websocket is connected.")
        return False
    try:
        response = ws["connection"].recv()
        return json.loads(response)
    except Exception:
        print("Failed to read websocket response")
        if ws["connection"]: # Ensure connection exists before trying to close
            ws["connection"].close()
        ws["isInited"] = False
    return False

def close_ws_connection() -> None:
    """
    Closes the active WebSocket connection and resets the connection state.
    """
    if ws["connection"]: # Ensure connection exists before trying to close
        ws["connection"].close()
    ws["isInited"] = False
