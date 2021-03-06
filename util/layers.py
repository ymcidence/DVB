import tensorflow as tf


def conv_layer(name, bottom, kernel_size, stride, output_dim, padding='SAME',
               bias_term=True, weights_initializer=None, biases_initializer=None):
    # input has shape [batch, in_height, in_width, in_channels]
    input_dim = bottom.get_shape().as_list()[-1]

    # weights and biases variables
    with tf.variable_scope(name):
        # initialize the variables
        if weights_initializer is None:
            weights_initializer = tf.random_normal_initializer(stddev=0.01)
        if bias_term and biases_initializer is None:
            biases_initializer = tf.constant_initializer(0.)

        # filter has shape [filter_height, filter_width, in_channels, out_channels]
        weights = tf.get_variable("weights",
                                  [kernel_size, kernel_size, input_dim, output_dim],
                                  initializer=weights_initializer)
        if bias_term:
            biases = tf.get_variable("biases", output_dim,
                                     initializer=biases_initializer)

    conv = tf.nn.conv2d(bottom, filter=weights,
                        strides=[1, stride, stride, 1], padding=padding)
    if bias_term:
        conv = tf.nn.bias_add(conv, biases)
    return conv


def conv_relu_layer(name, bottom, kernel_size, stride, output_dim, padding='SAME',
                    bias_term=True, weights_initializer=None, biases_initializer=None):
    conv = conv_layer(name, bottom, kernel_size, stride, output_dim, padding,
                      bias_term, weights_initializer, biases_initializer)
    relu = tf.nn.relu(conv)
    return relu


def deconv_layer(name, bottom, kernel_size, stride, output_dim, padding='SAME',
                 bias_term=True, weights_initializer=None, biases_initializer=None):
    # input_shape is [batch, in_height, in_width, in_channels]
    input_shape = bottom.get_shape().as_list()
    batch_size, input_height, input_width, input_dim = input_shape
    output_shape = [batch_size, input_height * stride, input_width * stride, output_dim]

    # weights and biases variables
    with tf.variable_scope(name):
        # initialize the variables
        if weights_initializer is None:
            weights_initializer = tf.random_normal_initializer(stddev=0.01)
        if bias_term and biases_initializer is None:
            biases_initializer = tf.constant_initializer(0.)

        # filter has shape [filter_height, filter_width, out_channels, in_channels]
        weights = tf.get_variable("weights",
                                  [kernel_size, kernel_size, output_dim, input_dim],
                                  initializer=weights_initializer)
        if bias_term:
            biases = tf.get_variable("biases", output_dim,
                                     initializer=biases_initializer)

    deconv = tf.nn.conv2d_transpose(bottom, filter=weights,
                                    output_shape=output_shape, strides=[1, stride, stride, 1],
                                    padding=padding)
    if bias_term:
        deconv = tf.nn.bias_add(deconv, biases)
    return deconv


def deconv_relu_layer(name, bottom, kernel_size, stride, output_dim, padding='SAME',
                      bias_term=True, weights_initializer=None, biases_initializer=None):
    deconv = deconv_layer(name, bottom, kernel_size, stride, output_dim, padding,
                          bias_term, weights_initializer, biases_initializer)
    relu = tf.nn.relu(deconv)
    return relu


def pooling_layer(name, bottom, kernel_size, stride, padding='SAME'):
    pool = tf.nn.max_pool(bottom, ksize=[1, kernel_size, kernel_size, 1],
                          strides=[1, stride, stride, 1], padding=padding, name=name)
    return pool


def fc_layer(name, bottom, output_dim, bias_term=True, weights_initializer=None,
             biases_initializer=None):
    # flatten bottom input
    # input has shape [batch, in_height, in_width, in_channels]
    shape = bottom.get_shape().as_list()
    input_dim = 1
    for d in shape[1:]:
        input_dim *= d
    flat_bottom = tf.reshape(bottom, [-1, input_dim])

    # weights and biases variables
    with tf.variable_scope(name):
        # initialize the variables
        if weights_initializer is None:
            weights_initializer = tf.random_normal_initializer(stddev=0.01)
        if bias_term and biases_initializer is None:
            biases_initializer = tf.constant_initializer(0.)

        # weights has shape [input_dim, output_dim]
        weights = tf.get_variable("weights", [input_dim, output_dim],
                                  initializer=weights_initializer)
        if bias_term:
            biases = tf.get_variable("biases", output_dim,
                                     initializer=biases_initializer)
    if bias_term:
        fc = tf.nn.xw_plus_b(flat_bottom, weights, biases)
    else:
        fc = tf.matmul(flat_bottom, weights)
    return fc


def fc_relu_layer(name, bottom, output_dim, bias_term=True,
                  weights_initializer=None, biases_initializer=None):
    fc = fc_layer(name, bottom, output_dim, bias_term, weights_initializer,
                  biases_initializer)
    relu = tf.nn.relu(fc)
    return relu


def one_hot_encoding(labels, num_classes, scope=None):
    """Transform numeric labels into onehot_labels.
    Args:
      labels: [batch_size] target labels.
      num_classes: total number of classes.
      scope: Optional scope for name_scope.
    Returns:
      one hot encoding of the labels.
    """
    with tf.name_scope(scope, 'OneHotEncoding', [labels]):
        batch_size = labels.get_shape()[0]
        indices = tf.expand_dims(tf.range(0, batch_size), 1)
        labels = tf.cast(tf.expand_dims(labels, 1), indices.dtype)
        concated = tf.concat([indices, labels], 1)
        onehot_labels = tf.sparse_to_dense(
            concated, tf.pack([batch_size, num_classes]), 1.0, 0.0)
        onehot_labels.set_shape([batch_size, num_classes])
        return onehot_labels


def conv_normalization_layer(batch_data, train=tf.constant(True, tf.bool), beta=None, eps=None):
    """

    :param batch_data:
    :param train:
    :param beta:
    :param eps:
    :return:
    """
    batch_mean, batch_var = tf.nn.moments(batch_data, [0, 1, 2])
    ema = tf.train.ExponentialMovingAverage(decay=0.5)

    def mean_var_with_update():
        ema_apply_op = ema.apply([batch_mean, batch_var])
        with tf.control_dependencies([ema_apply_op]):
            return tf.identity(batch_mean), tf.identity(batch_var)

    mean, var = tf.cond(train, mean_var_with_update, lambda: (ema.average(batch_mean), ema.average(batch_var)))
    n_out = batch_data.get_shape().as_list()[-1]
    if beta is None:
        beta = tf.Variable(tf.constant(0.0, shape=[n_out]), name='BNBeta', trainable=True)
    if eps is None:
        eps = tf.Variable(tf.constant(1.0, shape=[n_out]), name='BNGamma', trainable=True)

    return tf.nn.batch_normalization(batch_data, mean, var, beta, eps, 1e-3)


def conv_layer_with_pad(name, bottom, kernel_size, stride, output_dim, pad_size, padding='VALID',
                        bias_term=True, weights_initializer=None, biases_initializer=None):
    # input has shape [batch, in_height, in_width, in_channels]
    input_dim = bottom.get_shape().as_list()[-1]

    # weights and biases variables
    with tf.variable_scope(name):
        # initialize the variables
        padded_bottom = tf.pad(bottom, [[0, 0], [pad_size, pad_size], [pad_size, pad_size], [0, 0]])

        if weights_initializer is None:
            weights_initializer = tf.random_normal_initializer(stddev=0.01)
        if bias_term and biases_initializer is None:
            biases_initializer = tf.constant_initializer(0.)

        # filter has shape [filter_height, filter_width, in_channels, out_channels]
        weights = tf.get_variable("weights",
                                  [kernel_size, kernel_size, input_dim, output_dim],
                                  initializer=weights_initializer)
        if bias_term:
            biases = tf.get_variable("biases", output_dim,
                                     initializer=biases_initializer)

    conv = tf.nn.conv2d(padded_bottom, filter=weights,
                        strides=[1, stride, stride, 1], padding=padding)
    if bias_term:
        conv = tf.nn.bias_add(conv, biases)
    return conv


def conv_relu_layer_with_pad(name, bottom, kernel_size, stride, output_dim, pad_size, padding='VALID', bias_term=True,
                             weights_initializer=None, biases_initializer=None):
    return tf.nn.relu(conv_layer_with_pad(name, bottom, kernel_size, stride, output_dim, pad_size, padding=padding,
                                          bias_term=bias_term, weights_initializer=weights_initializer,
                                          biases_initializer=biases_initializer))
