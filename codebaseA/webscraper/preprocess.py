import msgpack
import json
import gc
from typing import List, Dict, Any, Tuple

# channel [0] == food
# channel [1] == winner snake
# channel [2] == other snakes

DIRS: List[Dict[str, int]] = [
    {"X":-1, "Y":0}, # left
    {"X":0, "Y":-1}, # up
    {"X":1, "Y":0}, # right
    {"X":0, "Y":1}, # down
]

# with open('sampleGame.json', 'r') as f:
#     data = json.load(f)

with open('finaldata/data.msgpack', 'rb') as f:
    data = msgpack.load(f)

def _get_winner_direction_encoding(
    current_state: Dict[str, Any],
    next_state: Dict[str, Any],
    winner_id: str,
    x_idx: int,
    y_idx: int
) -> List[int]:
    """
    Calculates the direction of the winner snake's movement between two states
    and returns it as a one-hot encoded list.

    Args:
        current_state: The game state at the current frame, containing snake positions.
        next_state: The game state at the subsequent frame, containing snake positions.
        winner_id: The ID of the winning snake.
        x_idx: The index (0 or 1) for the X coordinate, considering potential flipping.
        y_idx: The index (0 or 1) for the Y coordinate, considering potential flipping.

    Returns:
        A 4-element list representing the one-hot encoded direction (left, up, right, down).
    """
    winner_snake_current = next(filter(lambda s: s["id"] == winner_id, current_state["snakes"]))
    winner_snake_next = next(filter(lambda s: s["id"] == winner_id, next_state["snakes"]))

    head_pos_current = winner_snake_current["body"][0]
    head_pos_next = winner_snake_next["body"][0]

    # Calculate direction based on the chosen coordinate system (flipped or not)
    dir_delta = {
        "X": head_pos_next[x_idx] - head_pos_current[x_idx],
        "Y": head_pos_next[y_idx] - head_pos_current[y_idx]
    }

    dir_index = DIRS.index(dir_delta)
    encoded_dir = [0, 0, 0, 0]
    encoded_dir[dir_index] = 1
    return encoded_dir

def _initialize_empty_board(
    board_width: int,
    board_height: int,
    num_channels: int
) -> List[List[List[int]]]:
    """
    Initializes an empty 3D game board with specified dimensions and channels.

    Args:
        board_width: The width of the board (e.g., 11).
        board_height: The height of the board (e.g., 11).
        num_channels: The number of channels for each cell (e.g., 3 for food, winner, others).

    Returns:
        A 3D list representing the empty board, initialized with zeros.
    """
    board: List[List[List[int]]] = [[ [0] * num_channels for _ in range(board_height)] for _ in range(board_width)]
    return board

def _populate_snakes_on_board(
    board: List[List[List[int]]],
    snakes_data: List[Dict[str, Any]],
    winner_id: str,
    x_idx: int,
    y_idx: int
) -> None:
    """
    Populates the board with snake bodies and heads.

    Args:
        board: The 3D game board to populate (modified in-place).
        snakes_data: A list of dictionaries, each representing a snake's state.
        winner_id: The ID of the winning snake.
        x_idx: The index (0 or 1) for the X coordinate, considering potential flipping.
        y_idx: The index (0 or 1) for the Y coordinate, considering potential flipping.
    """
    for snake in snakes_data:
        # Channel 1 for winner snake, Channel 2 for other snakes
        channel = 1 if snake["id"] == winner_id else 2
        
        # Set snake head (value 5)
        head_pos = snake["body"][0]
        board[head_pos[x_idx]][head_pos[y_idx]][channel] = 5
        
        # Set other body parts (value 1)
        for i, body_part_pos in enumerate(snake["body"][1:]):
            board[body_part_pos[x_idx]][body_part_pos[y_idx]][channel] = 1

def _populate_food_on_board(
    board: List[List[List[int]]],
    food_data: List[List[int]],
    x_idx: int,
    y_idx: int
) -> None:
    """
    Populates the board with food items.

    Args:
        board: The 3D game board to populate (modified in-place).
        food_data: A list of food coordinates (e.g., [[x1, y1], [x2, y2]]).
        x_idx: The index (0 or 1) for the X coordinate, considering potential flipping.
        y_idx: The index (0 or 1) for the Y coordinate, considering potential flipping.
    """
    for food_pos in food_data:
        board[food_pos[x_idx]][food_pos[y_idx]][0] = 1 # Channel 0 for food

def preprocessGame(game: Dict[str, Any], flip: bool = False) -> List[Dict[str, Any]]:
    """
    Preprocesses a single game's states into a series of input-output frames
    suitable for a machine learning model. Each frame consists of a 3D board
    representation of the game state and a one-hot encoded direction chosen
    by the winner snake in the subsequent frame.

    Args:
        game: A dictionary containing the game data, including 'states' (list of game states)
              and 'winnerId' (ID of the winning snake).
        flip: If True, swaps the X and Y coordinates for board representation,
              effectively rotating the board by 90 degrees. Defaults to False.

    Returns:
        A list of dictionaries, where each dictionary contains:
        - "input": A 3D list representing the game board state for a given frame.
        - "output": A 4-element list representing the one-hot encoded direction
                    taken by the winner snake in the transition from the current
                    frame to the next.
    """
    frames: List[Dict[str, Any]] = []
    
    # Determine coordinate indices based on flip flag
    # If flip is True, original X (index 0) becomes Y, and original Y (index 1) becomes X.
    # So, x_idx points to the original Y coordinate, and y_idx points to the original X coordinate.
    x_idx: int = 1 if flip else 0
    y_idx: int = 0 if flip else 1

    board_width: int = 11
    board_height: int = 11
    num_channels: int = 3 # Food, Winner Snake, Other Snakes

    # Iterate through game states, excluding the last one as we need a 'next_state'
    for i in range(len(game["states"]) - 1):
        current_state = game["states"][i]
        next_state = game["states"][i+1]
        winner_id = game["winnerId"]

        # 1. Get direction chosen by winner snake and encode it
        encoded_dir = _get_winner_direction_encoding(
            current_state, next_state, winner_id, x_idx, y_idx
        )

        # 2. Initialize an empty 3D board for the current state
        board = _initialize_empty_board(board_width, board_height, num_channels)

        # 3. Populate the board with snakes from the current state
        _populate_snakes_on_board(
            board, current_state["snakes"], winner_id, x_idx, y_idx
        )

        # 4. Populate the board with food from the current state
        _populate_food_on_board(
            board, current_state["food"], x_idx, y_idx
        )

        frames.append({
            "input": board,
            "output": encoded_dir
        })
    return frames

preprocessed: List[Dict[str, Any]] = []
num: int = 0
for game in data:
    # The original code only processed the flipped version, keeping this behavior.
    # preprocessedGame = preprocessGame(game)
    # for frame in preprocessedGame:
    #     preprocessed.append(frame)
    preprocessedFlippedGame: List[Dict[str, Any]] = preprocessGame(game, True)
    for frame in preprocessedFlippedGame:
        preprocessed.append(frame)
    print(' '.join(["Game", str(num), ": Number of frames", str(len(preprocessed))]))
    num+=1

with open('data/preprocessed_data.msgpack', 'wb') as f:
    msgpack.dump(preprocessed, f)