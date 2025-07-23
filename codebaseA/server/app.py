
from flask import Flask, jsonify, request, Response

from snake import Snake

app = Flask(__name__)

snake = Snake()

DIRS: list[str] = [
    "left",
    "down",
    "right",
    "up"
]

@app.route("/", methods=['GET'])
def main() -> Response:
    """
    Handles the root endpoint ("/") with GET requests.
    This endpoint is typically used by the Battlesnake engine to retrieve
    basic information about the snake, such as its API version, author,
    color, head, tail, and game version.

    Returns:
        Response: A JSON response containing snake configuration details.
    """
    return jsonify({
        "apiversion": "1",
        "author": "danielisokayig",
        "color": "#FF0000",
        "head": "fang",
        "tail": "bolt",
        "version": "0.0.1-beta"
    })

@app.route("/start", methods=['POST'])
def start() -> str:
    """
    Handles the "/start" endpoint with POST requests.
    This endpoint is called at the beginning of each game.
    It can be used to initialize game-specific data or reset the snake's state.

    Returns:
        str: An empty string, as no specific response is required by the engine.
    """
    return ""

@app.route("/move", methods=['POST'])
def move() -> Response:
    """
    Handles the "/move" endpoint with POST requests.
    This is the main game logic endpoint, called each turn.
    It receives the current game state and determines the snake's next move.

    Returns:
        Response: A JSON response containing the chosen move direction
                  ("up", "down", "left", "right") and an optional shout message.
    """
    content: dict = request.json
    id: str = content["you"]["id"]
    snakes: list[dict] = [x for x in content["board"]["snakes"]]
    food: list[dict] = [x for x in content["board"]["food"]]
    return jsonify({
        "move": DIRS[snake.update(id, snakes, food)],
        "shout": "In the fog of great chaos shines the light of great opportunity."
    })

@app.route("/end", methods=['POST'])
def end() -> str:
    """
    Handles the "/end" endpoint with POST requests.
    This endpoint is called at the end of each game.
    It can be used for cleanup or logging game results.

    Returns:
        str: An empty string, as no specific response is required by the engine.
    """
    return ""
