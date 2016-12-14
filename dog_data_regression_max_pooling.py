# -*- coding: utf-8 -*-
"""
Created on Sun Dec 11 13:53:15 2016

@author: yamane
"""

import os
import numpy as np
import time
import tqdm
import copy
import matplotlib.pyplot as plt
from multiprocessing import Process, Queue
from chainer import cuda, optimizers, Chain, serializers
import chainer.functions as F
import chainer.links as L
import dog_data_regression


# ネットワークの定義
class Convnet(Chain):
    def __init__(self):
        super(Convnet, self).__init__(
            conv1=L.Convolution2D(3, 16, 3, stride=2, pad=1),
            norm1=L.BatchNormalization(16),
            conv2=L.Convolution2D(16, 16, 3, stride=2, pad=1),
            norm2=L.BatchNormalization(16),
            conv3=L.Convolution2D(16, 32, 3, stride=2, pad=1),
            norm3=L.BatchNormalization(32),
            conv4=L.Convolution2D(32, 32, 3, stride=2, pad=1),
            norm4=L.BatchNormalization(32),
            conv5=L.Convolution2D(32, 64, 3, stride=2, pad=1),
            norm5=L.BatchNormalization(64),

            norm6=L.BatchNormalization(64),
            l1=L.Linear(64, 1)
        )

    def network(self, X, test):
        h = self.conv1(X)
        h = self.norm1(h, test=test)
        h = F.relu(h)
        h = F.relu(self.norm2(self.conv2(h), test=test))
        h = F.relu(self.norm3(self.conv3(h), test=test))
        h = F.relu(self.norm4(self.conv4(h), test=test))
        h = F.relu(self.norm5(self.conv5(h), test=test))
        h = F.relu(self.norm6(F.max_pooling_2d(h, 7), test=test))
        y = self.l1(h)
        return y

    def forward(self, X, test):
        y = self.network(X, test)
        return y

    def lossfun(self, X, t, test):
        y = self.forward(X, test)
        loss = F.mean_squared_error(y, t)
        return loss

    def loss_ave(self, queue, num_batches, test):
        losses = []
        for i in range(num_batches):
            X_batch, T_batch = queue.get()
            X_batch = cuda.to_gpu(X_batch)
            T_batch = cuda.to_gpu(T_batch)
            loss = self.lossfun(X_batch, T_batch, test)
            losses.append(cuda.to_cpu(loss.data))
        return np.mean(losses)

    def predict(self, X, test):
        X = cuda.to_gpu(X)
        y = self.forward(X, test)
        y = cuda.to_cpu(y.data)
        return y


if __name__ == '__main__':
    file_name = os.path.splitext(os.path.basename(__file__))[0]
    time_start = time.time()
    image_list = []
    epoch_loss = []
    epoch_valid_loss = []
    loss_valid_best = np.inf
    r_loss = []

    # 超パラメータ
    max_iteration = 150  # 繰り返し回数
    batch_size = 100  # ミニバッチサイズ
    num_train = 20000  # 学習データ数
    num_test = 100  # 検証データ数
    learning_rate = 0.001  # 学習率
    output_size = 256  # 生成画像サイズ
    crop_size = 224  # ネットワーク入力画像サイズ
    aspect_ratio_min = 1.0  # 最小アスペクト比の誤り
    aspect_ratio_max = 3  # 最大アスペクト比の誤り
    file_path = r'E:\stanford_Dogs_Dataset\raw_dataset_binary\output_size_500\output_size_500.hdf5'  # データセットファイル保存場所
    output_location = 'C:\Users\yamane\Dropbox\correct_aspect_ratio'  # 学習結果保存場所
    # 学習結果保存フォルダ作成
    output_root_dir = os.path.join(output_location, file_name)
    output_root_dir = os.path.join(output_root_dir, str(time_start))
    if os.path.exists(output_root_dir):
        pass
    else:
        os.makedirs(output_root_dir)
    # ファイル名を作成
    model_filename = str(file_name) + str(time_start) + '.npz'
    loss_filename = 'epoch_loss' + str(time_start) + '.png'
    r_dis_filename = 'r_distance' + str(time_start) + '.png'
    model_filename = os.path.join(output_root_dir, model_filename)
    loss_filename = os.path.join(output_root_dir, loss_filename)
    r_dis_filename = os.path.join(output_root_dir, r_dis_filename)
    # バッチサイズ計算
    train_data = range(0, num_train)
    test_data = range(num_train, num_train + num_test)
    num_batches_train = num_train / batch_size
    num_batches_test = num_test / batch_size
    # キューを作成、プロセススタート
    queue_train = Queue(10)
    process_train = Process(target=dog_data_regression.create_mini_batch,
                            args=(queue_train, file_path, train_data,
                                  batch_size, aspect_ratio_min,
                                  aspect_ratio_max, crop_size, output_size))
    process_train.start()
    queue_valid = Queue(10)
    process_valid = Process(target=dog_data_regression.create_mini_batch,
                            args=(queue_valid, file_path, test_data,
                                  batch_size, aspect_ratio_min,
                                  aspect_ratio_max, crop_size, output_size))
    process_valid.start()
    queue_test = Queue(1)
    process_test = Process(target=dog_data_regression.create_mini_batch,
                           args=(queue_test, file_path, test_data,
                                 1, aspect_ratio_min, aspect_ratio_max,
                                 crop_size, output_size))
    process_test.start()
    # モデル読み込み
    model = Convnet().to_gpu()
    # Optimizerの設定
    optimizer = optimizers.Adam(learning_rate)
    optimizer.setup(model)

    time_origin = time.time()
    try:
        for epoch in range(max_iteration):
            time_begin = time.time()
            losses = []
            accuracies = []
            for i in tqdm.tqdm(range(num_batches_train)):
                X_batch, T_batch = queue_train.get()
                X_batch = cuda.to_gpu(X_batch)
                T_batch = cuda.to_gpu(T_batch)
                # 勾配を初期化
                optimizer.zero_grads()
                # 順伝播を計算し、誤差と精度を取得
                loss = model.lossfun(X_batch, T_batch, False)
                # 逆伝搬を計算
                loss.backward()
                optimizer.update()
                losses.append(cuda.to_cpu(loss.data))

            time_end = time.time()
            epoch_time = time_end - time_begin
            total_time = time_end - time_origin
            epoch_loss.append(np.mean(losses))

            loss_valid = model.loss_ave(queue_valid, num_batches_test, True)
            epoch_valid_loss.append(loss_valid)
            if loss_valid < loss_valid_best:
                loss_valid_best = loss_valid
                epoch__loss_best = epoch
                model_best = copy.deepcopy(model)

            # 訓練データでの結果を表示
            print "dog_data_regression.py"
            print "epoch:", epoch
            print "time", epoch_time, "(", total_time, ")"
            print "loss[train]:", epoch_loss[epoch]
            print "loss[valid]:", loss_valid
            print "loss[valid_best]:", loss_valid_best

            plt.plot(epoch_loss)
            plt.plot(epoch_valid_loss)
            plt.ylim(0, 0.5)
            plt.title("loss")
            plt.legend(["train", "valid"], loc="upper right")
            plt.grid()
            plt.show()

            # テスト用のデータを取得
            X_test, T_test = queue_test.get()
            r_loss = dog_data_regression.test_output(model_best, X_test, T_test, r_loss)

    except KeyboardInterrupt:
        print "割り込み停止が実行されました"

    plt.plot(epoch_loss)
    plt.plot(epoch_valid_loss)
    plt.ylim(0, 0.5)
    plt.title("loss")
    plt.legend(["train", "valid"], loc="upper right")
    plt.grid()
    plt.savefig(loss_filename)
    plt.show()

    plt.plot(r_loss)
    plt.title("r_disdance")
    plt.grid()
    plt.savefig(r_dis_filename)
    plt.show()

    model_filename = os.path.join(output_root_dir, model_filename)
    serializers.save_npz(model_filename, model_best)

    process_train.terminate()
    process_test.terminate()
    print 'max_iteration:', max_iteration
    print 'learning_rate:', learning_rate
    print 'batch_size:', batch_size
    print 'train_size', num_train
    print 'valid_size', num_test
    print 'output_size', output_size
    print 'crop_size', crop_size
    print 'aspect_ratio_min', aspect_ratio_min
    print 'aspect_ratio_max', aspect_ratio_max

    model_filename = os.path.join(output_root_dir, model_filename)
    serializers.save_npz(model_filename, model_best)

    process_train.terminate()
    process_test.terminate()
    print 'max_iteration:', max_iteration
    print 'learning_rate:', learning_rate
    print 'batch_size:', batch_size
    print 'train_size', num_train
    print 'valid_size', num_test
    print 'output_size', output_size
    print 'crop_size', crop_size
    print 'aspect_ratio_min', aspect_ratio_min
    print 'aspect_ratio_max', aspect_ratio_max
