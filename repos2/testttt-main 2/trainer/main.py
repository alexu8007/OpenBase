import tensorflow as tf
import numpy as np
import msgpack
import json

data = None
input_shape = (11, 11, 3)
num_classes = 4
num_datasets = 12

# with open("data.json", "r") as f:
#     data = json.load(f)

# load the saved model
# model = tf.keras.models.load_model('model.h5')
# create new model
model = tf.keras.Sequential([
    tf.keras.layers.Conv2D(32, kernel_size=(3, 3), activation='relu', padding='same', input_shape=input_shape),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2), padding='same'),
    tf.keras.layers.Conv2D(64, kernel_size=(3, 3), activation='relu', padding='same'),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2), padding='same'),
    tf.keras.layers.Conv2D(64, kernel_size=(3, 3), activation='relu', padding='same'),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2), padding='same'),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dense(num_classes, activation='softmax')
])
model.compile(loss='categorical_crossentropy', optimizer='sgd', metrics=['accuracy'])

dataset_num = 0

while True:
    # get dataset
    with open("finaldata/{}.msgpack".format(dataset_num), "rb") as f:
        data = msgpack.load(f)
    x_train = np.array((sample['input'] for sample in data))
    y_train = np.array((sample['output'] for sample in data))
    # train the model on the dataset
    model.fit(x_train, y_train, batch_size=32, epochs=5, validation_split=0.04)
    # save the model
    print("Saving model...")
    model.save('model.h5', overwrite=True)
    # switch to next dataset
    dataset_num+=1
    dataset_num%=num_datasets