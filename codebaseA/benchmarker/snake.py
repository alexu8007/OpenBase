from pyray import *
import random
import tensorflow as tf
import numpy as np
from typing import List, Dict, Any, Optional

from constants import *
from formatBoard import format_board

# Type aliases for clarity
Position = Dict[str, int] # {"x": int, "y": int}

model = tf.keras.models.load_model('dense.h5')
COLS = [GREEN, BLUE, PINK, YELLOW, ORANGE, PURPLE]
# Directions for snake movement: Up, Down, Left, Right
DIRS = [{"x": 0, "y": -1}, {"x": 0, "y": 1}, {"x": -1, "y": 0}, {"x": 1, "y": 0}]

class Snake:
    """
    Represents a single snake in the game, controlled by a neural network.
    Manages its position, tail, movement, and collision detection.
    """
    def __init__(self, x: int, y: int, snake_id: int) -> None:
        """
        Initializes a new Snake instance.

        Args:
            x: The initial x-coordinate of the snake's head.
            y: The initial y-coordinate of the snake's head.
            snake_id: A unique identifier for the snake.
        """
        self.x: int = x
        self.y: int = y
        self.id: int = snake_id
        self.tail: List[Position] = []
        # Using random.choice for color is acceptable as it's not security-critical game logic.
        self.color: Color = random.choice(COLS)
        self.is_dead: bool = False

        # Initialize tail with two segments at the head's starting position
        for enum_idx, _ in enumerate(range(2)):
            self.tail.append({"x": self.x, "y": self.y})

    def update(self, snakes: List['Snake'], food: List[Position]) -> None:
        """
        Updates the snake's state, including its position, tail, and checks for collisions.

        Args:
            snakes: A list of all active snakes in the game.
            food: A list of food positions on the board.
        """
        if self.is_dead:
            return

        self._update_tail_position()
        next_move_dir = self._determine_next_move(snakes, food)
        self._apply_move(next_move_dir)
        self._check_food_collision(food)

    def _update_tail_position(self) -> None:
        """
        Updates the positions of the snake's tail segments.
        Each segment moves to the position of the segment in front of it.
        The first segment moves to the head's previous position.
        """
        if not self.tail: # Should not happen if initialized correctly, but good for safety
            return

        # Move all tail segments to the position of the segment in front of them
        for enum_idx, i in enumerate(reversed(range(1, len(self.tail)))):
            self.tail[i]["x"] = self.tail[i-1]["x"]
            self.tail[i]["y"] = self.tail[i-1]["y"]

        # Move the first tail segment to the head's previous position
        self.tail[0]["x"] = self.x
        self.tail[0]["y"] = self.y

    def _determine_next_move(self, snakes: List['Snake'], food: List[Position]) -> Position:
        """
        Determines the next move for the snake using the neural network.
        It tries to find the best move that doesn't immediately kill the snake.

        Args:
            snakes: A list of all active snakes in the game.
            food: A list of food positions on the board.

        Returns:
            A dictionary representing the chosen direction (e.g., {"x": 0, "y": -1}).
        """
        alive_snakes = (s for s in snakes if not s.is_dead)
        model_input = np.array(format_board(self, alive_snakes, food)).reshape(1, 11, 11, 3)
        prediction = list(model.predict(model_input, verbose=0)[0])

        # Sort possible moves by their predicted value in descending order
        # Each item is {"index": DIRS index, "value": prediction score}
        possible_moves = sorted(
            ({"index": i, "value": prediction[i]} for i in range(len(prediction))),
            key=lambda a: a["value"],
            reverse=True
        )

        chosen_dir: Optional[Position] = None
        for move_data in possible_moves:
            potential_dir = DIRS[move_data["index"]]
            new_x = self.x + potential_dir["x"]
            new_y = self.y + potential_dir["y"]
            if not self._is_collision_at_position(new_x, new_y, list(alive_snakes), for_future_move=True):  # Convert generator back to list for this call
                chosen_dir = potential_dir
                break

        # If all moves are terrible, just pick the one with the highest prediction
        if chosen_dir is None:
            chosen_dir = DIRS[prediction.index(max(prediction))]

        return chosen_dir

    def _is_collision_at_position(self, check_x: int, check_y: int,
                                   all_snakes: List['Snake'], for_future_move: bool = False) -> bool:
        """
        Checks if a given position (check_x, check_y) results in a collision
        with walls, any snake's head (excluding self), or any snake's tail.

        Args:
            check_x: The x-coordinate to check.
            check_y: The y-coordinate to check.
            all_snakes: A list of all active snakes in the game.
            for_future_move: If True, considers the last segment of own tail
                             as not a collision, as it will move.

        Returns:
            True if a collision would occur, False otherwise.
        """
        # Check wall collision
        if not (0 <= check_x < BOARD_WIDTH and 0 <= check_y < BOARD_HEIGHT):
            return True

        for snake in all_snakes:
            # Check collision with other snake's head
            if snake.id != self.id and check_x == snake.x and check_y == snake.y:
                return True

            # Check collision with any snake's tail
            for i, piece in enumerate(snake.tail):
                if check_x == piece["x"] and check_y == piece["y"]:
                    # If checking for a future move and it's our own last tail segment,
                    # it's not a collision because it will move out of the way.
                    if for_future_move and snake.id == self.id and i == len(snake.tail) - 1:
                        continue
                    return True
        return False

    def _apply_move(self, direction: Position) -> None:
        """
        Applies the chosen movement direction to the snake's head.

        Args:
            direction: The direction to move (e.g., {"x": 1, "y": 0}).
        """
        self.x += direction["x"]
        self.y += direction["y"]

    def _check_food_collision(self, food: List[Position]) -> None:
        """
        Checks if the snake's head has collided with any food item.
        If a collision occurs, the food is removed, and the snake grows.

        Args:
            food: A list of food positions on the board.
        """
        for piece in food:
            if self.x == piece["x"] and self.y == piece["y"]:
                food.remove(piece)
                # Add a new tail segment at the position of the last segment
                # before it moved. This effectively makes the snake grow.
                if self.tail:
                    last_segment = self.tail[-1]
                    self.tail.append({"x": last_segment["x"], "y": last_segment["y"]})
                else: # Fallback, though tail should always be initialized
                    self.tail.append({"x": self.x, "y": self.y})
                break # Only eat one piece of food per update

    def should_be_dead(self, snakes: List['Snake']) -> None:
        """
        Determines if the snake should be marked as dead based on various collision rules.
        This method updates the `is_dead` status of the snake.

        Args:
            snakes: A list of all active snakes in the game.
        """
        if self.is_dead:
            return

        # Check wall collision
        if not (0 <= self.x < BOARD_WIDTH and 0 <= self.y < BOARD_HEIGHT):
            self.is_dead = True
            return

        # Check collision with own tail (excluding the very first segment which is where head was)
        for piece in self.tail[1:]:
            if self.x == piece["x"] and self.y == piece["y"]:
                self.is_dead = True
                return

        # Check collision with other snakes' heads or tails
        for snake in snakes:
            if snake.is_dead:
                continue
            if snake.id == self.id: # Skip self, already checked own tail
                continue

            # Collision with another snake's head
            if self.x == snake.x and self.y == snake.y:
                self.is_dead = True
                return

            # Collision with another snake's tail
            tail_positions = set((piece["x"], piece["y"]) for piece in snake.tail)
            if (self.x, self.y) in tail_positions:
                self.is_dead = True
                return

    def draw(self) -> None:
        """
        Draws the snake (head and tail) on the game board with full opacity.
        """
        # Draw head
        draw_rectangle(int(self.x * GS_WIDTH), int(self.y * GS_HEIGHT),
                       int(GS_WIDTH), int(GS_HEIGHT), color_alpha(self.color, 0.8))
        # Draw tail
        for piece in self.tail:
            draw_rectangle(int(piece["x"] * GS_WIDTH), int(piece["y"] * GS_HEIGHT),
                           int(GS_WIDTH), int(GS_HEIGHT), self.color)

    def draw_dead(self) -> None:
        """
        Draws the snake (head and tail) on the game board with reduced opacity,
        indicating it is dead.
        """
        # Draw head
        draw_rectangle(int(self.x * GS_WIDTH), int(self.y * GS_HEIGHT),
                       int(GS_WIDTH), int(GS_HEIGHT), color_alpha(self.color, 0.2))
        # Draw tail
        for piece in self.tail:
            draw_rectangle(int(piece["x"] * GS_WIDTH), int(piece["y"] * GS_HEIGHT),
                           int(GS_WIDTH), int(GS_HEIGHT), color_alpha(self.color, 0.2))