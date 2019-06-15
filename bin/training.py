from keras.callbacks import ModelCheckpoint, TensorBoard, ReduceLROnPlateau, CSVLogger, LambdaCallback
import logging
import matplotlib.pyplot as plt
from .custom_classes.DataRescaler import DataRescaler
from .custom_classes.DataGenerator import DataGenerator
import numpy as np
from tqdm import tqdm

class ModelTrainer(object):

    def __init__(self, model, training_generator, valid_generator, batch_size,
                 epochs, run_id, outpath, workers, shuffling):
        self.model = model
        self.training_generator = training_generator
        self.valid_generator = valid_generator
        self.batch_size = batch_size
        self.epochs = epochs
        self.run_id = run_id
        self.outpath = outpath
        self.workers = workers
        self.shuffle = shuffling

    def plot_prediction(self, epoch, logs):
        pred_gen = self.valid_generator

        n_iter = 4 * self.batch_size
        image_array = np.zeros((n_iter, pred_gen[0][0][0].shape[1], pred_gen[0][0][0].shape[2], pred_gen[0][0][0].shape[3]))
        dship_array = np.zeros((n_iter, pred_gen[0][0][1].shape[1]))
        lidar_array = np.zeros((n_iter))
        lidar_array[:] = -777
        for i in np.arange(0, n_iter, self.batch_size):
            image_array[i: i+self.batch_size] = pred_gen[i][0][0]
            dship_array[i: i+self.batch_size] = pred_gen[i][0][1]
            lidar_array[i: i+self.batch_size] = pred_gen[i][1]

        logging.debug(f"lidar_array Max: {lidar_array.max()} | Min: {lidar_array.min()} | Median: {np.median(lidar_array)}")
        logging.debug(f"dship_array Max: {dship_array.max()} | Min: {dship_array.min()} | Median: {np.median(dship_array)}")
        logging.debug(f"image_array Max: {image_array.max()} | Min: {image_array.min()} | Median: {np.median(image_array)}")

        predx = [image_array, dship_array]

        predout_raw = self.model.predict(predx, batch_size=self.batch_size)
        predout = DataRescaler().rescale(predout_raw.copy(), vmin=-1, vmax=10000)
        predy = DataRescaler().rescale(lidar_array.copy(), vmin=-1, vmax=10000)

        fig, (ax, ax2) = plt.subplots(nrows=2)
        ax.plot(predout, color="red", label=f"Predicted Max:{predout.max():.2f} | Min:{predout.min():.2f}\n"
        f"Max_raw:{predout_raw.max():.2f} | Min:{predout_raw.min():.2f}")
        ax.plot(predy, color="green", label=f"Truth Max:{predy.max():.2f} | Min:{predy.min():.2f}\n"
        f"Max_raw:{lidar_array.max():.2f} | Min:{lidar_array.min():.2f}")
        ax.set_ylabel("CBH [m]")
        ax.set_ylim(0, 10000)
        ax.legend(loc="upper left")

        ax2.plot(predout, color="red", label="Predicted")
        ax2.plot(predy, color="green", label="Truth")
        ax2.set_ylabel("CBH [m]")
        ax2.set_ylim(0, 1000)
        ax2.legend(loc="upper left")

        plt.savefig(self.outpath + str(self.run_id) + f"/preds_{epoch}.png")
        plt.close(fig)

    def train_model(self):
        filepath = self.outpath + str(self.run_id) + "/weights-improvement-{epoch:02d}.hdf5"
        logging.info(f"Will write checkpoints to: {filepath}")
        checkpoint = ModelCheckpoint(filepath, verbose=1, save_best_only=False, save_weights_only=False, mode='min',
                                     monitor='val_loss',)
        callbacks_list = [checkpoint]
        tb_logdir = f"./tb_log/{self.run_id}/"
        logging.debug(f"Tensorboard logdir at: {tb_logdir}")
        callbacks_list.append(TensorBoard(log_dir=tb_logdir, histogram_freq=0, write_graph=True, write_images=False,
                                     write_grads=True, update_freq="batch", batch_size=self.batch_size))
        callbacks_list.append(ReduceLROnPlateau(patience=5, factor=0.5))
        callbacks_list.append(CSVLogger(filename=self.outpath + str(self.run_id) + "/train_log.csv"))
        # callbacks_list.append(LambdaCallback(on_epoch_end=self.plot_prediction))

        self.model.fit_generator(generator=self.training_generator,
                                 validation_data=self.valid_generator,
                                 use_multiprocessing=True, workers=self.workers,
                                 epochs=self.epochs, shuffle=self.shuffle,
                                 callbacks=callbacks_list)