import tensorflow as tf
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

from formatBoard import format_board

model = tf.keras.models.load_model('big3.h5')

DIRS: List[Dict[str, int]] = [
    {"x": -1, "y": 0}, # left
    {"x": 0, "y": -1}, # down
    {"x": 1, "y": 0}, # right
    {"x": 0, "y": 1}, # up
]

class Snake:
    """
    A class representing the AI logic for a snake in a game.
    It uses a pre-trained TensorFlow model to predict the best next move
    and includes logic to avoid immediate collisions.
    """

    def _get_our_snake_position(self, snake_id: str, snakes: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Identifies and returns the head coordinates of the current snake.

        Args:
            snake_id: The unique identifier of the current snake.
            snakes: A list of dictionaries, each representing a snake in the game,
                    including its ID and body segments.

        Returns:
            A tuple (x, y) representing the current snake's head coordinates.
        """
        this_snake = next(filter(lambda snake: snake["id"] == snake_id, snakes))
        this_snake_x = int(this_snake["head"]["x"])
        this_snake_y = int(this_snake["head"]["y"])
        return this_snake_x, this_snake_y

    def _get_model_prediction(self, snake_id: str, snakes: List[Dict[str, Any]], food: List[Dict[str, int]]) -> List[float]:
        """
        Generates a prediction from the TensorFlow model based on the current game state.

        Args:
            snake_id: The unique identifier of the current snake.
            snakes: A list of dictionaries, each representing a snake in the game.
            food: A list of dictionaries, each representing a food item's coordinates.

        Returns:
            A list of floats representing the model's confidence for each possible direction.
        """
        # format_board is assumed to convert game state into a suitable input for the model
        input_board = np.array(format_board(snake_id, snakes, food)).reshape(1, 11, 11, 3)
        prediction = list(model.predict(input_board)[0])
        print(prediction) # Keep original print for debugging/monitoring
        return prediction

    def is_a_terrible_move(self, snakes: List[Dict[str, Any]], this_snake_x: int, this_snake_y: int, best_move_info: Dict[str, Any]) -> bool:
        """
        Checks if a potential move would result in an immediate collision with walls or other snakes.

        Args:
            snakes: A list of dictionaries, each representing a snake in the game.
            this_snake_x: The current X-coordinate of the snake's head.
            this_snake_y: The current Y-coordinate of the snake's head.
            best_move_info: A dictionary containing the 'index' of the chosen direction
                            (0: left, 1: down, 2: right, 3: up) and its 'value'.

        Returns:
            True if the move is terrible (leads to collision), False otherwise.
        """
        best_dir = DIRS[best_move_info["index"]]
        new_x = this_snake_x + best_dir["x"]
        new_y = this_snake_y + best_dir["y"]

        # Check for wall collision
        if new_x > 10 or new_x < 0 or new_y > 10 or new_y < 0:
            return True

        occupied = set((piece["x"], piece["y"]) for snake in snakes for piece in snake["body"])
        if (new_x, new_y) in occupied:
            print("terrible move", this_snake_x, this_snake_y, new_x, new_y)
            return True
        return False

    def _find_best_valid_move(self, prediction: List[float], snakes: List[Dict[str, Any]], this_snake_x: int, this_snake_y: int) -> Optional[Dict[str, Any]]:
        """
        Iterates through predicted moves, from best to worst, to find the first one
        that is not considered 'terrible'.

        Args:
            prediction: A list of floats representing the model's confidence for each direction.
            snakes: A list of dictionaries, each representing a snake in the game.
            this_snake_x: The current X-coordinate of the snake's head.
            this_snake_y: The current Y-coordinate of the snake's head.

        Returns:
            A dictionary containing the 'index' and 'value' of the best valid move,
            or None if all predicted moves are terrible.
        """
        generator = ({"index": i, "value": prediction[i]} for i in range(len(prediction)))
        possibles = sorted(generator, key=lambda a: a["value"])  # Sorts in ascending order

        best_valid_move: Optional[Dict[str, Any]] = None
        while possibles:
            current_best = possibles.pop()  # Get the highest value prediction
            if not self.is_a_terrible_move(snakes, this_snake_x, this_snake_y, current_best):
                best_valid_move = current_best
                break
        return best_valid_move

    def update(self, snake_id: str, snakes: List[Dict[str, Any]], food: List[Dict[str, int]]) -> int:
        """
        Determines the best next move for the snake based on model prediction and safety checks.

        Args:
            snake_id: The unique identifier of the current snake.
            snakes: A list of dictionaries, each representing a snake in the game.
            food: A list of dictionaries, each representing a food item's coordinates.

        Returns:
            An integer representing the index of the chosen direction:
            0: left, 1: down, 2: right, 3: up.
        """
        this_snake_x, this_snake_y = self._get_our_snake_position(snake_id, snakes)
        prediction = self._get_model_prediction(snake_id, snakes, food)

        best_move = self._find_best_valid_move(prediction, snakes, this_snake_x, this_snake_y)

        # If all moves are terrible, revert to the model's absolute best prediction
        # (even if it's terrible, to avoid crashing the snake)
        if best_move is None:
            return prediction.index(max(prediction))
        else:
            return best_move["index"]