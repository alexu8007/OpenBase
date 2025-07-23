import random
import secrets
import uuid
import json
from typing import List, Dict, Any, Tuple

# Assuming pyray, Snake, and constants are available as before
from pyray import *  # type: ignore # pyray might not have type hints
from snake import Snake
from constants import *

# Global game state variables
# These are kept global as per the original structure, but functions
# are designed to interact with them cleanly or pass them where needed.
# For a larger application, encapsulating these in a GameState class would be ideal.
snakes: List[Snake] = []
food: List[Dict[str, int]] = []
turn: int = 0
snake_lengths_at_turn_end: List[int] = []
benchmark_data: List[Dict[str, Any]] = []

if IS_GRAPHICAL:
    init_window(800, 800, "Snake")
    set_target_fps(FRAME_RATE)

def _initialize_game_state() -> Tuple[List[Snake], List[Dict[str, int]], int]:
    """
    Initializes the game state, including snakes, food, and turn counter.

    Returns:
        A tuple containing:
        - A list of initialized Snake objects.
        - An empty list for food positions.
        - The initial turn count (0).
    """
    initialized_snakes = (Snake(loc["x"], loc["y"], uuid.uuid1()) for loc in SPAWN_LOCS)
    initialized_food: List[Dict[str, int]] = []
    initial_turn = 0
    return initialized_snakes, initialized_food, initial_turn

def _spawn_initial_food(snakes: List[Snake], food_list: List[Dict[str, int]]) -> None:
    """
    Spawns initial food items on the board, relative to snake spawn locations,
    and adds a central food item.

    Args:
        snakes: A list of Snake objects.
        food_list: The list to which food positions will be added.
    """
    # Using random.choice for non-security-critical game logic.
    # For cryptographic randomness (e.g., secure token generation),
    # the 'secrets' module should be used instead.
    # Example: secrets.choice(FOOD_LOCS)
    for snake in snakes:
        selection = random.choice(FOOD_LOCS)
        food_pos = {"x": selection["x"], "y": selection["y"]}
        food_pos["x"] += snake.x
        food_pos["y"] += snake.y
        food_list.append(food_pos)
    food_list.append({"x": int(BOARD_WIDTH / 2), "y": int(BOARD_HEIGHT / 2)})

def _is_valid_food_position(pos: Dict[str, int], snakes: List[Snake]) -> bool:
    """
    Checks if a given position is valid for spawning food (i.e., not on a snake's body).

    Args:
        pos: A dictionary with 'x' and 'y' coordinates.
        snakes: A list of Snake objects.

    Returns:
        True if the position is valid, False otherwise.
    """
    return not any(
        piece["x"] == pos["x"] and piece["y"] == pos["y"]
        for snake in snakes
        if not snake.is_dead
        for piece in snake.tail
    )

def _spawn_random_food(food_list: List[Dict[str, int]], snakes: List[Snake]) -> None:
    """
    Attempts to spawn a new food item at a random valid position on the board.
    Food spawns with a 1 in 8 chance each turn.

    Args:
        food_list: The list to which new food positions will be added.
        snakes: A list of Snake objects to check for valid positions.
    """
    # Using random.randint for non-security-critical game logic.
    # For cryptographic randomness (e.g., secure key generation),
    # the 'secrets' module should be used instead.
    # Example: secrets.randbelow(8) == 0 (for 1 in 8 chance)
    if random.randint(1, 8) == 1:
        pos = {"x": 0, "y": 0}
        while True:
            pos["x"] = random.randint(0, BOARD_WIDTH - 1)
            pos["y"] = random.randint(0, BOARD_HEIGHT - 1)
            if _is_valid_food_position(pos, snakes):
                food_list.append(pos)
                break

def _update_all_snakes(snakes: List[Snake], food_list: List[Dict[str, int]]) -> Tuple[List[int], int]:
    """
    Updates the state of all snakes (movement, eating, collision checks).

    Args:
        snakes: A list of Snake objects.
        food_list: The list of food positions.

    Returns:
        A tuple containing:
        - A list of current lengths for all snakes (including dead ones).
        - The number of snakes still alive.
    """
    current_snake_lengths: List[int] = []
    num_snakes_remaining = 0
    for snake in snakes:
        current_snake_lengths.append(len(snake.tail) + 1)
        if not snake.is_dead:
            num_snakes_remaining += 1
            snake.update(snakes, food_list)
    for snake in snakes:
        snake.should_be_dead(snakes) # Check for collisions after all snakes have moved
    return current_snake_lengths, num_snakes_remaining

def _draw_game_elements(snakes: List[Snake], food_list: List[Dict[str, int]]) -> None:
    """
    Draws all game elements on the screen, including snakes and food.
    This function is only called if IS_GRAPHICAL is True.

    Args:
        snakes: A list of Snake objects to draw.
        food_list: A list of food positions to draw.
    """
    # Draw snakes
    for snake in snakes:
        if not snake.is_dead:
            snake.draw()
        else:
            snake.draw_dead()
    # Draw food
    for food_item in food_list:
        draw_ellipse(
            int(food_item["x"] * GS_WIDTH + GS_WIDTH / 2),
            int(food_item["y"] * GS_HEIGHT + GS_HEIGHT / 2),
            int(GS_WIDTH / 2),
            int(GS_HEIGHT / 2),
            RED
        )

def run_game_loop() -> Tuple[int, List[int]]:
    """
    Executes the main game loop, handling turns, updates, drawing, and game end conditions.

    Returns:
        A tuple containing:
        - The total number of turns played.
        - A list of the final lengths of all snakes at the end of the game.
    """
    global snakes, food, turn, snake_lengths_at_turn_end

    snakes, food, turn = _initialize_game_state()
    _spawn_initial_food(snakes, food)

    num_snakes_remaining = len(snakes) # Initialize with all snakes alive

    while not ((window_should_close() if IS_GRAPHICAL else False) or num_snakes_remaining <= 1):
        if IS_GRAPHICAL:
            begin_drawing()
            clear_background(GRAY)

        turn += 1
        snake_lengths_at_turn_end, num_snakes_remaining = _update_all_snakes(snakes, food)

        if IS_GRAPHICAL:
            _draw_game_elements(snakes, food)

        _spawn_random_food(food, snakes)

        if IS_GRAPHICAL:
            end_drawing()

    if IS_GRAPHICAL and window_should_close():
        # If the window was closed, the game ended by user action, not by game rules.
        # We still return the current state.
        pass

    return turn, snake_lengths_at_turn_end

# --- Main execution block ---

for i, _ in enumerate(range(NUM_BENCHMARKS)):
    print(' '.join(['Benchmarking', 'game', str(i+1), '/', str(NUM_BENCHMARKS)]))
    final_turn, final_snake_lengths = run_game_loop()
    print(' '.join(['\tturns:', str(final_turn), 'lengths:', str(final_snake_lengths)]))
    benchmark_data.append({
        "turns": final_turn,
        "lengths": final_snake_lengths
    })

with open("benchmark_data.json", "w") as f:
    json.dump(benchmark_data, f, indent=4)

if IS_GRAPHICAL:
    close_window()