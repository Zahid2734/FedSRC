from utils.functions_new import  fed_avg,batch_data_new, get_masked_model_chatgpt, SimpleMLP, save_file,  open_file, batch_data, set_model_weights, get_cropped_model_chatgpt, group_gradient, group_hessian_new, norm_grad
from utils.mnist_data_generator import*
from utils.math_function import weight_scalling_factor,fed_avg_weight,scale_model_weights,sum_scaled_weights,weight_std_dev_median
import tensorflow as tf
import numpy as np
import math
from tensorflow.keras import backend as K
import random
import os
os.environ['PYTHONHASHSEED'] = '0'
np.random.seed(37)
random.seed(5)
tf.random.set_seed(8)

# file_name = "../Dataset0.3_1_100_flip_mnist.pkl"
# Dataset= open_file(file_name)
Dataset_flip= mnist_noniid_flip_data(client_percent=.3, data_percent=1,num_clients=100)
Dataset_shuffle= mnist_noniid_shuffle_data(client_percent=.3, data_percent=1,num_clients=100)
Dataset_noisy= mnist_noniid_noise_data(client_percent=.3, data_percent=1,num_clients=100)
#process and batch the training data for each client
clients= Dataset_flip[0]
clients2= Dataset_shuffle[0]
clients3=Dataset_noisy[0]
clients.update(clients2)
clients.update(clients3)
clients_batched = dict()
clients_batched_test = dict()
for (client_name, data) in clients.items():
    clients_batched[client_name],clients_batched_test[client_name]= batch_data_new(data)

#process and batch the test set
bad_client_flip= Dataset_flip[1]
bad_client_shuffle= Dataset_shuffle[1]
bad_client_noisy= Dataset_noisy[1]

x_test= Dataset_flip[2]
y_test= Dataset_flip[3]
test_batched = tf.data.Dataset.from_tensor_slices((x_test, y_test)).batch(len(y_test))
client_names = list(clients_batched.keys())

print(client_names)

loss = 'categorical_crossentropy'
metrics = ['accuracy']
epochs = 300
lr = 0.001
alpha= 1
beta=1
batch_size = 32
client_percent= 1
bla = SimpleMLP
model = bla.build(784,1)
model.compile(loss=loss,
              optimizer=tf.keras.optimizers.Adam(
                  learning_rate=lr),
              metrics=metrics)
global_weight = model.get_weights()
initial_weight = model.get_weights()


group1_accuracy = []
group1_loss = []
group1_train_accuracy=[]
group1_train_loss=[]
global_accuracy = []
global_loss = []
global_weight_list=[]
taken_client = []
global_mean=0
global_standard_dev=0
bla=0

for i in range(epochs):
    print("group 1 training")
    model1_accuracy = []
    model1_loss = []
    model1_train_accuracy = []
    model1_train_loss = []
    model1_weight = []
    fileter1_block=[]
    fileter2_block=[]

    # randomlist = random.sample(range(0, 300), math.ceil(300 * client_percent))
    randomlist= [i for i in range(300)]
    taken_client.append(randomlist)
    total_data = []
    if i<299:
        for a in randomlist:
            data_points = len(clients_batched[client_names[a]]) * batch_size
            total_data.append(data_points)
            model.set_weights(global_weight)
            local_score = model.evaluate(clients_batched[client_names[a]], verbose=0)
            # if i % 1 == 0 and i > 0:
            #     score1 = model.evaluate(clients_batched_test[client_names[a]], verbose=1)
            #     model1_accuracy.append(score1[1])
            #     model1_loss.append(score1[0])
            model1_accuracy.append(local_score[1])
            model1_loss.append(local_score[0])
            hist1 = model.fit(clients_batched[client_names[a]], epochs=1, verbose=1)
            weight1 = np.array(model.get_weights())
            model1_train_accuracy.append(hist1.history['accuracy'][-1])
            model1_train_loss.append(hist1.history['loss'][-1])
            model1_weight.append(weight1)
            K.clear_session()


    else:
        for a in randomlist:
            model.set_weights(global_weight)
            local_score = model.evaluate(clients_batched[client_names[a]], verbose=0)
            print('Evaluation loss: ',local_score[0])
            model1_accuracy.append(local_score[1])
            model1_loss.append(local_score[0])
            # if i % 10 == 0 and i > 0:
            #     score1 = model.evaluate(clients_batched_test[client_names[a]], verbose=1)
            #     model1_accuracy.append(score1[1])
            #     model1_loss.append(score1[0])
            #     # val= global_mean-local_score[0]

            if global_mean-max(global_standard_dev*2.5,2.5*bla) <=local_score[0]<=global_mean+max(global_standard_dev*alpha,alpha*bla):
                hist1 = model.fit(clients_batched[client_names[a]], epochs=1, verbose=1)
                # if abs(local_score[0]-hist1.history['loss'][-1])<= beta*global_standard_dev:

                weight1 = np.array(model.get_weights())
                model1_train_accuracy.append(hist1.history['accuracy'][-1])
                model1_train_loss.append(hist1.history['loss'][-1])
                model1_weight.append(weight1)
                data_points = len(clients_batched[client_names[a]]) * batch_size
                total_data.append(data_points)

                K.clear_session()

            else:
                fileter1_block.append(a)
                print('blocked at filter1')

    if i==10:
        bla = np.std(model1_train_loss)
        print('bla: ',bla)

    print(model1_train_loss)

    if len(model1_train_accuracy)>0:
        group1_accuracy.append(model1_accuracy)
        group1_loss.append(model1_loss)
        group1_train_accuracy.append(model1_train_accuracy)
        group1_train_loss.append(model1_train_loss)
        global_mean, global_standard_dev= np.mean(group1_train_loss[-1]), np.std(group1_train_loss[-1])
        print(f'mean is {global_mean} and Standard deviation {global_standard_dev}')
        weighted_value = fed_avg_weight(total_data)
        scaled_weight = list()
        for k in range(len(weighted_value)):
            scaled_weight.append(scale_model_weights(model1_weight[k], weighted_value[k]))

        # to get the average over all the local model, we simply take the sum of the scaled weights
        global_weight = sum_scaled_weights(scaled_weight)
    else:
        global_mean=global_mean
        global_weight=global_weight
        global_standard_dev=global_standard_dev

    model.set_weights(global_weight)
    model.evaluate(x_test, y_test)
    score = model.evaluate(x_test, y_test, verbose=0)
    print('communication round:', i)
    print("Test loss:", score[0])
    print("Test accuracy:", score[1])
    global_accuracy.append(score[1])
    global_loss.append(score[0])

    if i%10==0 and i>0:
        global_weight_list.append(global_weight)
        sample_list = [global_accuracy, global_loss, group1_train_accuracy, group1_train_loss, group1_accuracy, group1_loss, global_weight_list, bad_client_flip, bad_client_shuffle, bad_client_flip]
        save_file_name= f'../data/fedavg Mnist flip shuffle noisy_train_test.pkl'
        save_file(save_file_name, sample_list)

