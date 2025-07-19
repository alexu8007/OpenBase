
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
    board = []
    for j in range(11):
        board.append([])
        for k in range(11):
            board[j].append([])
            for l in range(3):
                board[j][k].append(0)
    # add snakes
    for s in snakes:
        if s.id == snake.id:
            continue
        board[s.tail[0]["x"]][s.tail[0]["y"]][2] = 5
        for j in range(len(s.tail)-1):
            board[s.tail[j+1]["x"]][s.tail[j+1]["y"]][2] = 1
    # add this snake
    board[snake.tail[0]["x"]][snake.tail[0]["y"]][1] = 5
    for j in range(len(snake.tail)-1):
        board[snake.tail[j+1]["x"]][snake.tail[j+1]["y"]][1] = 1
    # add food
    for f in food:
        board[f["x"]][f["y"]][0] = 1
    return board
