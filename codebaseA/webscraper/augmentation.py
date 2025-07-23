
import msgpack
import numpy as np
from typing import List, Dict, Any

DIRS: List[Dict[str, int]] = [
    {"X": -1, "Y": 0},  # left
    {"X": 0, "Y": -1},  # up
    {"X": 1, "Y": 0},   # right
    {"X": 0, "Y": 1},   # down
]

SOURCES: int = 3

def rotate_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rotates a single frame's input array 90 degrees counter-clockwise and
    updates its corresponding output direction.

    The input array is expected to be a 2D list (e.g., a grid), and the
    output is a one-hot encoded list representing a direction (e.g., [0,0,1,0] for right).

    Args:
        frame (Dict[str, Any]): A dictionary representing a frame, with keys:
            - "input" (List[List[int]]): The 2D input array.
            - "output" (List[int]): The one-hot encoded output direction.

    Returns:
        Dict[str, Any]: A new frame dictionary with the rotated input array
                        and the updated output direction.
    """
    # rotate the input array
    rotated_array: List[List[int]] = np.rot90(np.array(frame["input"])).tolist()
    
    # rotate the output direction
    dir_index: int = frame["output"].index(1)
    dir_index += 1 # rotation counter clockwise 90 degrees
    dir_index %= 4
    
    # one hot encode output direction
    rotated_dir: List[int] = [0,0,0,0]
    rotated_dir[dir_index] = 1
    
    return {
        "input": rotated_array,
        "output": rotated_dir
    }

def process_and_save_source_data(source_index: int, total_sources: int) -> None:
    """
    Loads data for a given source, applies a single rotation to each frame,
    and saves the preprocessed data multiple times with different filenames
    based on a 'rotation' index.

    Note: The original logic effectively applies only one rotation to each frame
    regardless of the 'dir' loop, which primarily affects the output filename.

    Args:
        source_index (int): The index of the data source (e.g., 0, 1, 2).
        total_sources (int): The total number of sources defined in the global constant.
    """
    input_filepath: str = 'data/{}.msgpack'.format(source_index)

    with open(input_filepath, 'rb') as f:
        data: List[Dict[str, Any]] = msgpack.load(f)

    for dir_idx in range(3):
        preprocessed_frames: List[Dict[str, Any]] = []
        for frame in data:
            # The original code had a loop 'for x in range(dir_idx+1)'
            # which applied rotations to a 'rotated_frame' variable,
            # but then discarded its result and appended 'rotateFrame(frame)'
            # (a single rotation of the original frame) to 'preprocessed'.
            # We replicate this exact (potentially unintended) behavior.
            preprocessed_frames.append(rotate_frame(frame))
            
        print(f"Source {source_index}, Rotation {dir_idx}, Number of frames {len(preprocessed_frames)}")
        
        output_filepath: str = 'data/{}.msgpack'.format(total_sources + source_index * 3 + dir_idx)
        with open(output_filepath, 'wb') as f:
            msgpack.dump(preprocessed_frames, f)

def main() -> None:
    """
    Main function to orchestrate the data preprocessing pipeline.
    It iterates through defined data sources, loads their frames,
    applies rotations, and saves the results to new files.
    """
    for source_idx in range(SOURCES):
        process_and_save_source_data(source_idx, SOURCES)

if __name__ == "__main__":
    main()

# [
#     [[0, 1, 0], [0, 0, 1], [0, 1, 0]],
#     [[0, 1, 0], [0, 0, 0], [0, 1, 0]],
#     [[1, 0, 1], [1, 0, 0], [0, 0, 0]]
# ]

# [
#     [[0, 1, 0], [0, 1, 0], [0, 0, 0]],
#     [[0, 0, 1], [0, 0, 0], [1, 0, 0]],
#     [[0, 1, 0], [0, 1, 0], [1, 0, 1]]
# ]
