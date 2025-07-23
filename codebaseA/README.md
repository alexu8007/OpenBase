# Machine Learning BattleSnake Tools

4 Python tools for creating tensorflow neural networks to play [BattleSnake](https://play.battlesnake.com/).

## webscraper

This tool uses BeautifulSoup to scrape the BattleSnake leaderboard for game data. It only considers games played by the top 10% of snakes (configurable) and filters out repeated games. The game data is saved into a .msgpack file which can then be preprocessed. Board states are quite large and so are the save files, this means that it is recommended to split the scraped data into multiple files which can be preprocessed and passed to the neural network separetly. The augmentation script takes preprocessed .msgpack files and rotates the board states by 90 degrees 3 times and outputs 3 new files for each input file representing the rotated data.

- main.py
  - Scrapes game data off of the top snakes on the BattleSnake leaderboard and saves it into a .msgpack file
- preprocess.py
  - Formats the scraped .msgpack data into frames which are readable by the neural network
- augmentation.py
  - Performs data augmentation on the preprocessed .msgpack files to multiply the amount of data by 4
- snakeCatcher.py
  - Utilty for scraping the BattleSnake website
- ws.py
  - Utility for handling websocket connections

## trainer

This tool takes preprocessed data from the webscraper and uses it to train a neural network. It uses pytorch to handle the network creation and training. Because the training files can get quite large, and python is memory hungry, you can split up the input data into multiple files which will be read and used for training independantly. The network should perform reasonably well after it reaches a cross validation accuracy of ~75%. If your network fails to reach ~60% accuracy after several epochs, it is likely that your training data is bad.

- main.py
  - Creates/loads and trains a convolutional neural network using pytorch and saves it as a .h5 file
- dense.py
  - Copy of main.py but modified to exclude convolutional layers

## benchmarker

This tool takes a trained neural network and benchmarks it against itself by simulating games. You can enable graphics with raylib in constants.py, as well as settings for how many benchmarks should be ran. The benchmark data will be outputed in a .json file and will contain information about how many turns the network is able to survive and what length it can reach.

- main.py
  - Simulates and benchmarks a network against itself and saves the benchmark data as a .json file
- constants.py
  - Constants specifying how networks should be benchmarked
- snake.py
  - Class to handle the operation of a snake in a benchmark
- formatBoard.py
  - Utility that formats the board state before being fed to the neural network
  
## server.py

This tool uses flask to host a trained neural network which responds to the BattleSnake v1 api. It handles formating the board data for the neural network, as well as generating a response. By default, the server will also check the network's responses to make sure that it doesn't make a move which will immediately lead to its death. This failsafe system sometimes prevents the network from making a valid move in the case where the snake is trying to move into the end of its tail (which will have moved by the next frame).

- app.py
  - Flask server which hosts a neural network with the BattleSnake v1 api
- snake.py
  - Operates the neural network and feeds the results back to the server
- formatBoard.py
  - Utility that formats the board state before being fed to the neural network
