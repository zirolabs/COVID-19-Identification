import numpy as np
import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

from keras.preprocessing.image import ImageDataGenerator
from keras.utils import to_categorical
from keras.callbacks import ModelCheckpoint, EarlyStopping, TensorBoard

from keras.applications.inception_v3 import InceptionV3
from keras import layers as nn
from keras.models import Model
from keras import optimizers as optim

import matplotlib.pyplot as plt
from tqdm import tqdm
from glob import glob

from skimage.io import imread
from skimage.transform import resize

from sklearn.model_selection import StratifiedShuffleSplit


def load_data():
    # TODO: Replace with flow from dir
    # data paths
    DATA_DIR = './Lung Images'
    DATA_PATHS = glob(f'{DATA_DIR}/*/*.jpg')

    with open(f'{DATA_DIR}/discard_list') as f:
        discard_set = set([l.strip() for l in f.readlines()])

    imgs = np.empty((len(DATA_PATHS) - len(discard_set), 299, 299, 3))

    labels = []
    i = 0
    for impath in tqdm(DATA_PATHS):
        _, src, fname = impath.split('\\')
        if(src == 'China-Tuberculosis'):
            # the label is tha last character of the filename
            label = fname.split('.')[0][-1]
            pass
        elif(src == 'Covid-19'):
            if(fname in discard_set):
                continue
            label = 2
            pass
        else:
            label = 0
            pass
        img = imread(impath, as_gray=False)
        img = resize(img, (299, 299))
        imgs[i, :] = img/255.
        labels.append(label)
        i += 1

    np.save('data/processed_input.npy', imgs)
    np.save('data/labels.npy', np.array(labels))


# training variables
INPUT_SHAPE = (299, 299, 3)
BATCH_SIZE = 32
EPOCHS = 50
LEARNING_RATE = 1e-3
LR_DECAY = LEARNING_RATE/EPOCHS

X = np.load('data/processed_input.npy', mmap_mode='r')
y = np.load('data/labels.npy')

s_splitter = StratifiedShuffleSplit(n_splits=1, 
                                    test_size=.2, 
                                    random_state=42)

train_index, test_index = next(s_splitter.split(X, y))

# load base model and freeze learning
base_model = InceptionV3(weights="imagenet", include_top=False,
                         input_tensor=nn.Input(shape=INPUT_SHAPE))
for layer in base_model.layers:
    layer.trainable = False

# add trainable layers
x = base_model.output
x = nn.AveragePooling2D(pool_size=(4, 4))(x)
x = nn.Flatten(name="flatten")(x)
x = nn.Dense(64, activation="relu")(x)
x = nn.Dropout(.5)(x)
x = nn.Dense(64, activation="relu")(x)
x = nn.Dropout(.5)(x)
output = nn.Dense(3, activation="softmax")(x)

model = Model(inputs=base_model.input, outputs=output)
model.compile(loss='categorical_crossentropy',
              optimizer=optim.Adam(lr=LEARNING_RATE, 
                                 decay=LR_DECAY), 
              metrics=['accuracy', 'mse'])


X_train = X[train_index]
y_train = to_categorical(y[train_index])

X_test  = X[test_index]
y_test  = to_categorical(y[test_index])
imagen = ImageDataGenerator(
    rotation_range=20,
    width_shift_range=0.2,
    height_shift_range=0.2,
    horizontal_flip=True)

es_c = EarlyStopping(monitor='val_loss', patience=3, mode='min')
mc_c = ModelCheckpoint(f'serialized/model.h5',
                       monitor='val_loss',
                       save_best_only=True,
                       mode='min', verbose=1)
tb_c = TensorBoard(log_dir='./serialized/logs')

history = model.fit_generator(imagen.flow(X_train,
                                            y_train,
                                            batch_size=BATCH_SIZE),
                            steps_per_epoch=len(X_train) // BATCH_SIZE,
                            epochs=EPOCHS,
                            callbacks=[es_c, mc_c, tb_c],
                            verbose=1, 
                            validation_data=(X_test, y_test))