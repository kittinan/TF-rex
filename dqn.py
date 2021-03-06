import numpy as np
import tensorflow as tf
import random
import os
from tools import conv2d, linear


class DQN:

    def __init__(self, session, height, width, num_actions, name, path=None):

        if path is not None:
            if os.path.exists(path):
                print "PATH FOR STORING RESULTS ALREADY EXISTS!"
                exit(1)
            os.makedirs(path)

        self.save_cnt = 0
        self.path = path
        self.num_actions = num_actions
        self.height = height
        self.width = width
        self.name = name
        self.vars = []

        self._create_network()

        self.session = session
        self.saver = tf.train.Saver()

    def get_action_and_q(self, states):
        """
        returns array:
            array[0]: actions: is a array of length len(state) with the action with the highest score
            array[1]: q value: is a array of length len(state) with the Q-value belonging to the action
        """
        states = states.reshape(-1, self.height, self.width, 1)
        return self.session.run([self.a, self.Q], {self.state: states})

    def get_action(self, states):
        """
        returns action(s),
            - if states contains only a single state then we return the optimal action as an integer,
            - if states contains an array of states then we return the optimal action for each state of the array
        """
        states = states.reshape(-1, self.height, self.width, 1)
        num_states = states.shape[0]
        actions = self.session.run(self.a, {self.state: states})
        return actions[0] if num_states == 1 else actions

    def train(self, states, actions, targets):
        states = states.reshape(-1, self.height, self.width, 1)
        feed_dict = {self.state: states, self.actions: actions, self.Q_target: targets}
        self.session.run(self.minimize, feed_dict)

    def save(self):
        if self.path is not None:
            self.saver.save(self.session, self.path + '/model', global_step = self.save_cnt)
            self.save_cnt += 1

    def tranfer_variables_from(self, other):
        """
            Builds the operations required to transfer the values of the variables
            from other to self
        """
        ops = []
        for var_self, var_other in zip(self.vars, other.vars):
            ops.append(var_self.assign(var_other.value()))

        self.session.run(ops)


    def _create_network(self):

        with tf.variable_scope(self.name):
            self.state =  tf.placeholder(shape=[None, self.height, self.width, 1],dtype=tf.float32)

            conv1, w1, b1 = conv2d(self.state, 32, [8, 8, 1, 32], [4, 4], "conv1")
            conv2, w2, b2 = conv2d(conv1, 64, [4, 4, 32, 64], [2, 2], "conv2")
            conv3, w3, b3 = conv2d(conv2, 64, [3, 3, 64, 64], [1, 1], "conv3")
            self.vars += [w1, b1, w2, b2, w3, b3]

            shape = conv3.get_shape().as_list()
            conv3_flat = tf.reshape(conv3, [-1, reduce(lambda x, y: x * y, shape[1:])])

            # Dueling
            value_hid, w4, b4 = linear(conv3_flat, 512, "value_hid")
            adv_hid, w5, b5 = linear(conv3_flat, 512, "adv_hid")

            value, w6, b6 = linear(value_hid, 1, "value", activation_fn=None)
            advantage, w7, b7 = linear(adv_hid, self.num_actions, "advantage", activation_fn=None)
            self.vars += [w4, b4, w5, b5, w6, b6, w7, b7]

            # Average Dueling
            self.Qs = value + (advantage - tf.reduce_mean(advantage, axis=1, keep_dims=True))

            # action with highest Q values
            self.a = tf.argmax(self.Qs, 1)
            # Q value belonging to selected action
            self.Q = tf.reduce_max(self.Qs, 1)

            # For training
            self.Q_target = tf.placeholder(shape=[None], dtype=tf.float32)
            self.actions = tf.placeholder(shape=[None], dtype=tf.int32)
            actions_onehot = tf.one_hot(self.actions, self.num_actions, on_value=1., off_value=0., axis=1, dtype=tf.float32)

            Q_tmp = tf.reduce_sum(tf.multiply(self.Qs, actions_onehot), axis=1)
            loss = tf.reduce_mean(tf.square(self.Q_target - Q_tmp))
            optimizer = tf.train.AdamOptimizer()
            self.minimize = optimizer.minimize(loss)


class Memory:

    def __init__(self, size):
        self.size = size
        self.mem = np.ndarray((size,5), dtype=object)
        self.iter = 0
        self.current_size = 0

    def add(self, state1, action, reward, state2, crashed):
        self.mem[self.iter,:] = state1, action, reward, state2, crashed
        self.iter = (self.iter + 1) % self.size
        self.current_size = min(self.current_size + 1, self.size)

    def sample(self, n):
        n = min(self.current_size, n)
        random_idx = random.sample(range(self.current_size), n)
        sample = self.mem[random_idx]
        return (np.stack(sample[:,i], axis=0) for i in range(5))
