# this stuff can be edited
NUM_BENCHMARKS = 25
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
IS_GRAPHICAL = True # performance isnt bottlenecked by graphics but this is an option anyways
FRAME_RATE = 1000

# this stuff shouldnt be touched
BOARD_WIDTH = 11
BOARD_HEIGHT = 11
GS_WIDTH = SCREEN_WIDTH/BOARD_WIDTH
GS_HEIGHT = SCREEN_HEIGHT/BOARD_HEIGHT
SPAWN_LOCS = [
    {"x": 1, "y": 1}, # top left
    {"x": 9, "y": 1}, # top right
    {"x": 9, "y": 9}, # bottom right
    {"x": 1, "y": 9}, # bottom left
]
FOOD_LOCS = [
    {"x": -1, "y": -1}, # top left
    {"x": 1, "y": -1}, # top right
    {"x": 1, "y": 1}, # bottom right
    {"x": -1, "y": 1}, # bottom left
]
DIRS = [
    {"x": -1, "y": 0}, # left
    {"x": 0, "y": -1}, # up
    {"x": 1, "y": 0}, # right
    {"x": 0, "y": 1}, # down
]