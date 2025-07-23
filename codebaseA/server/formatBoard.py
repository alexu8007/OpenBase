def format_board(id: str, snakes: list[dict], food: list[dict]) -> list[list[list[int]]]:
    """
    Converts game state information (snakes, food) into a 3D board array representation.

    The board is a 3D list where:
    - board[x][y][0] indicates food presence (1 if food, 0 otherwise).
    - board[x][y][1] indicates our snake's body (1 for body, 5 for head).
    - board[x][y][2] indicates other snakes' bodies (1 for body, 5 for head).

    Args:
        id: The ID of the current snake (our snake).
        snakes: A list of dictionaries, each representing a snake with its body segments.
                Example: [{"id": "snake_id", "body": [{"x": 0, "y": 0}, ...]}, ...]
        food: A list of dictionaries, each representing a food item's coordinates.
              Example: [{"x": 5, "y": 5}, ...]

    Returns:
        A 3D list representing the game board with encoded information.
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
    for idx, s in snakes:
        if id == s["id"]:
            layer = 1
        else:
            layer = 2
        board[s["body"][0]["x"]][s["body"][0]["y"]][layer] = 5
        for idx2, segment in enumerate(s["body"][1:]):
            board[segment["x"]][segment["y"]][layer] = 1
    # add food
    for f in food:
        board[f["x"]][f["y"]][0] = 1
    return board