# -*- coding: utf-8 -*-
"""
Created on Thu Dec 01 04:13:19 2016

@author: yamane
"""

import numpy as np
import matplotlib.pyplot as plt
import cv2
from chainer import cuda, serializers, Variable
import toydata
import toydata_regression
import toydata_regression_ave_pooling


def generate_image(model, X, T, max_iteration, a):
    X_data = Variable(cuda.to_gpu(X))
    for epoch in range(max_iteration):
        print epoch
        y = model.forward(X_data, True)
        y.grad = cuda.cupy.ones(y.data.shape, dtype=np.float32)
        y.backward(retain_grad=True)
        X_data = Variable(X_data.data + a * X_data.grad)
        X_new = cuda.to_cpu(X_data.data)
        X_new = X_new.reshape(-1, 224, 224)
    print 'origin_T:', T[0], 'exp(origin_T):', np.exp(T[0])
    print 'new_T:', y.data[0], 'exp(new_T):', cuda.cupy.exp(y.data[0])
    # 元のXを表示
#        print 'origin_T:', T[0], 'exp(origin_T):', np.exp(T[0])
    plt.matshow(X[0][0], cmap=plt.cm.gray)
    plt.title("origin_X")
    plt.colorbar()
    plt.show()
    # 最適化後のXを表示
#        print 'new_T:', y.data[0], 'exp(new_T):', cuda.cupy.exp(y.data[0])
    plt.matshow(X_new[0], cmap=plt.cm.gray)
    plt.title("new_X")
    plt.colorbar()
    plt.show()
    return X_new


def get_receptive_field(y):
    # 特徴マップを取得
    a = y.creator.inputs[0]
    l = []
    while a.creator:
        if a.creator.label == 'ReLU':
            l.append(cuda.to_cpu(a.data))
        a = a.creator.inputs[0]
    return l


def check_use_channel(l, layer):
    use_channel = []
    layer = len(l) - layer
    for c in range(l[layer].shape[1:2][0]):
        temp = []
        for b in range(batch_size):
            temp.append(np.sum(l[layer][b][c]))
        ave = np.average(temp)
        use_channel.append(ave)
    return use_channel


def minibatch_regression(dataset, batch_size, r):
    images = []
    ts = []

    for i in range(batch_size):
        image = dataset.create_image()
        image = toydata.change_aspect_ratio(image, r)
        square_image = toydata.padding_image(image)
        # cv2.resize:(image, (w, h))
        # transform.resize:(image, (h, w))
        resize_image = cv2.resize(
            square_image, (dataset.output_size, dataset.output_size))
        resize_image = resize_image[..., None]
        images.append(resize_image)
        t = np.log(r)
        ts.append(t)
    X = np.stack(images, axis=0)
    X = np.transpose(X, (0, 3, 1, 2))
    X = X.astype(np.float32)
    T = np.array(ts, dtype=np.float32).reshape(-1, 1)
    return X, T

if __name__ == '__main__':
    # 超パラメータ
    max_iteration = 500  # 繰り返し回数
    batch_size = 1
    image_size = 500
    circle_r_min = 50
    circle_r_max = 150
    size_min = 199
    size_max = 200
    p = [0, 1, 0]
    output_size = 224
    aspect_ratio_max = 2
    aspect_ratio_min = 2
    step_size = 0.00001
    model_file= 'model1481172416.48toydata2.npz'

#    model = toydata_regression.Convnet().to_gpu()
#    serializers.load_npz('toydata_regression_min2.npz', model)
    model = toydata_regression.Convnet().to_gpu()
    serializers.load_npz(model_file, model)

    dataset = toydata.RandomCircleSquareDataset(
        image_size, circle_r_min, circle_r_max, size_min, size_max, p,
        output_size, aspect_ratio_max, aspect_ratio_min)
    # テストデータを取得
    X_yoko, T_yoko = minibatch_regression(dataset, batch_size, 2)
    X_tate, T_tate = minibatch_regression(dataset, batch_size, 0.5)
    # Rが大きくなるようにXを最適化する
    X_new = generate_image(model, X_yoko, T_yoko, max_iteration, step_size)

    X_yoko_gpu = Variable(cuda.to_gpu(X_yoko))
    X_tate_gpu = Variable(cuda.to_gpu(X_tate))
    # yを計算
    y_yoko = model.forward(X_yoko_gpu, True)
    y_tate = model.forward(X_tate_gpu, True)
    # 特徴マップを取得
    l_yoko = get_receptive_field(y_yoko)
    l_tate = get_receptive_field(y_tate)
    # 特徴マップを表示
#    for f in l_yoko[-1][0]:
#        plt.matshow(f, cmap=plt.cm.gray)
#        plt.show()
#    for f in l_tate[-1][0]:
#        plt.matshow(f, cmap=plt.cm.gray)
#        plt.show()
    l5_yoko = check_use_channel(l_yoko, 5)
    l4_yoko = check_use_channel(l_yoko, 4)
    l3_yoko = check_use_channel(l_yoko, 3)
    l2_yoko = check_use_channel(l_yoko, 2)
    l1_yoko = check_use_channel(l_yoko, 1)
    l5_tate = check_use_channel(l_tate, 5)
    l4_tate = check_use_channel(l_tate, 4)
    l3_tate = check_use_channel(l_tate, 3)
    l2_tate = check_use_channel(l_tate, 2)
    l1_tate = check_use_channel(l_tate, 1)

    plt.plot(l1_yoko)
    plt.plot(l1_tate)
    plt.title("layer1")
    plt.legend(["yoko", "tate"], loc="lower right")
    plt.show()
    plt.plot(l2_yoko)
    plt.plot(l2_tate)
    plt.title("layer2")
    plt.legend(["yoko", "tate"], loc="lower right")
    plt.show()
    plt.plot(l3_yoko)
    plt.plot(l3_tate)
    plt.title("layer3")
    plt.legend(["yoko", "tate"], loc="lower right")
    plt.show()
    plt.plot(l4_yoko)
    plt.plot(l4_tate)
    plt.title("layer4")
    plt.legend(["yoko", "tate"], loc="lower right")
    plt.show()
    plt.plot(l5_yoko)
    plt.plot(l5_tate)
    plt.title("layer5")
    plt.legend(["yoko", "tate"], loc="lower right")
    plt.show()
    # 出力に対する入力の勾配を可視化
    y_yoko.grad = cuda.cupy.ones(y_yoko.data.shape, dtype=np.float32)
    y_yoko.backward(retain_grad=True)
    grad = X_yoko_gpu.grad
    grad = cuda.to_cpu(grad)
    for c in grad[0]:
        plt.matshow(c, cmap=plt.cm.bwr)
        plt.title("yoko")
        plt.colorbar()
        plt.show()
    y_tate.grad = cuda.cupy.ones(y_tate.data.shape, dtype=np.float32)
    y_tate.backward(retain_grad=True)
    grad = X_tate_gpu.grad
    grad = cuda.to_cpu(grad)
    for c in grad[0]:
        plt.matshow(c, cmap=plt.cm.bwr)
        plt.title("tate")
        plt.colorbar()
        plt.show()
    for c in X_yoko[0]:
        plt.matshow(c, cmap=plt.cm.gray)
        plt.colorbar()
        plt.show()
    for c in X_tate[0]:
        plt.matshow(c, cmap=plt.cm.gray)
        plt.colorbar()
        plt.show()

    print 'max_iteration', max_iteration
    print 'batch_size', batch_size
    print 'image_size', image_size
    print 'output_size', output_size
    print 'aspect_ratio_max', aspect_ratio_max
    print 'aspect_ratio_min', aspect_ratio_min
    print 'step_size', step_size
    print 'model_file', model_file
