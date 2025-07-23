from typing import List, Dict, Any
from constants import *

def format_board(snake: Any, snakes: List[Any], food: List[Dict[str, int]]) -> List[List[List[int]]]:
    """
    Converts snake and food information into a 3D board array representation.

    The board is a 3D list where board[x][y][layer] represents the state of a cell.
    - Layer 0: Food (1 if food is present, 0 otherwise)
    - Layer 1: Your snake (5 for head, 1 for body, 0 otherwise)
    - Layer 2: Other snakes (5 for head, 1 for body, 0 otherwise)

    Args:
        snake: The current snake object (your snake), expected to have an 'id' attribute (str)
               and a 'tail' attribute (List[Dict[str, int]] where each dict has 'x' and 'y' keys).
        snakes: A list of other snake objects, each expected to have an 'id' attribute (str)
                and a 'tail' attribute (List[Dict[str, int]] where each dict has 'x' and 'y' keys).
        food: A list of food items, where each item is a dictionary
              with 'x' and 'y' integer keys.

    Returns:
        A 3D list representing the game board.
        The dimensions are [11][11][3], where 11x11 is the board size and 3 is for the layers.
    """
    # convert snake info to 2d board array
    board = [[[0 for _ in range(3)] for _ in range(11)] for _ in range(11)]
    # add snakes
    def add_snake(board, snake_tail, layer):
        if snake_tail:
            head = snake_tail[0]
            board[head["x"]][head["y"]][layer] = 5
            for idx, segment in enumerate(snake_tail[1:]):
                board[segment["x"]][segment["y"]][layer] = 1
    
    for s in snakes:
        if s.id == snake.id:
            continue
        add_snake(board, s.tail, 2)
    
    add_snake(board, snake.tail, 1)
    
    # add food
    for idx, f in enumerate(food):
        board[f["x"]][f["y"]][0] = 1
    return board