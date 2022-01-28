# -*- coding: utf-8 -*-
"""
Created on Thu Jan 27 20:46:14 2022

@author: pkinn
"""

#%% Imports
import tensorflow as tf
from holdout_utils import *
from onehot_gen import onehot_gen, shiftedColorMap
import matplotlib
from matplotlib.patches import Rectangle
import seaborn as sns
import matplotlib.pyplot as plt


#%% Load data into dataframes
emi_binding = pd.read_csv("emi_binding.csv", header = 0, index_col = 0)
iso_binding = pd.read_csv("iso_binding.csv", header = 0, index_col = 0)
igg_binding = pd.read_csv("igg_binding.csv", header = 0, index_col = 0)

#%% generate OHE features
emi_onehot = onehot_gen(emi_binding)
iso_onehot = onehot_gen(iso_binding)
igg_onehot = onehot_gen(igg_binding)

#%% Create dense model

modelCompression = tf.keras.models.Sequential([
    tf.keras.layers.Dense(10, activation = 'relu'),
    tf.keras.layers.Dense(1),
    tf.keras.layers.Dense(2)])

modelNormal = tf.keras.models.Sequential([
    tf.keras.layers.Dense(10, activation = 'relu'),
    tf.keras.layers.Dense(2)])

lossFn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True)

modelNormal.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])

modelNormal.fit(emi_onehot.values,  emi_binding['ANT Binding'].values, epochs = 10)

#%% Use k-fold CV
from sklearn.model_selection import KFold

kf = KFold(n_splits = 10, shuffle = True)
fn = 1
features = emi_onehot.values
batch_sz = 50
nepochs = 10
targets = emi_binding['ANT Binding'].values
# Define per-fold score containers <-- these are new
acc_per_fold = []
loss_per_fold = []
for train, test in kf.split(features, targets):
    
    model = tf.keras.models.Sequential([
        # tf.keras.layers.Dense(1, activation = 'relu'),
        tf.keras.layers.Dense(1),
        tf.keras.layers.Dense(2)])
    
    lossFn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True)
    
    model.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
    print('------------------------------------------------------------------------')
    print(f'Training for fold {fn} ...')
    
    history = model.fit(features[train], targets[train], 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)
    scores = model.evaluate(features[test], targets[test], verbose = 0)
    print(f'Score for fold {fn}: {model.metrics_names[0]} of {scores[0]}; {model.metrics_names[1]} of {scores[1]*100}%')
    acc_per_fold.append(scores[1] * 100)
    loss_per_fold.append(scores[0])
    fn += 1

#%% Create 2-layer projector-decider network
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, losses
from tensorflow.keras.models import Model

class projectorDecider(Model):
    def __init__(self, projDim, inputDim):
        super(projectorDecider, self).__init__()
        self.projDim = projDim
        self.inputDim = inputDim
        self.projector = tf.keras.Sequential([
            tf.keras.layers.InputLayer(input_shape = (self.inputDim)),
            # tf.keras.layers.Dense(100),
            tf.keras.layers.Dense(self.projDim)])
        self.decider = tf.keras.Sequential([
            tf.keras.layers.InputLayer(input_shape = (self.projDim,)),
            tf.keras.layers.Dense(2)])
    def call(self, x):
        projected = self.projector(x)
        decided = self.decider(projected)
        return decided


f = KFold(n_splits = 10, shuffle = True)
fn = 1
features = emi_onehot.values
batch_sz = 50
nepochs = 10
targets = emi_binding['ANT Binding'].values
# Define per-fold score containers <-- these are new
acc_per_fold = []
loss_per_fold = []
for train, test in kf.split(features, targets):

    pdModel = projectorDecider(1,2300)
    lossFn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True)
    
    pdModel.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
    print('------------------------------------------------------------------------')
    print(f'Training for fold {fn} ...')
    
    history = pdModel.fit(features[train], targets[train], 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)
    scores = pdModel.evaluate(features[test], targets[test], verbose = 0)
    print(f'Score for fold {fn}: {model.metrics_names[0]} of {scores[0]}; {model.metrics_names[1]} of {scores[1]*100}%')
    acc_per_fold.append(scores[1] * 100)
    loss_per_fold.append(scores[0])
    fn += 1
#%% Train "final" models

pdModelAnt = projectorDecider(1, 2300)
targetsAnt = emi_binding['ANT Binding'].values
lossFn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True)
pdModelAnt.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
pdModelAnt.fit(features, targetsAnt, 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)

pdModelPsy = projectorDecider(1, 2300)
pdModelPsy.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
targetsPsy = emi_binding['OVA Binding'].values
pdModelPsy.fit(features, targetsPsy, 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)

#%% Project isolated OHE features and compare w/ data
projIsoAnt = pdModelAnt.projector(iso_onehot.values)
plt.figure()
plt.scatter(projIsoAnt, iso_binding['ANT Binding'].values)
plt.xlabel('NN Projection')
plt.ylabel('Measured ANT binding')
antCorr = sc.stats.spearmanr(projIsoAnt, iso_binding['ANT Binding'].values)


projIsoPsy = pdModelPsy.projector(iso_onehot.values)
plt.figure()
plt.scatter(projIsoPsy, iso_binding['OVA Binding'].values)
plt.xlabel('NN Projection')
plt.ylabel('Measured OVA binding')
ovaCorr = sc.stats.spearmanr(projIsoPsy, iso_binding['OVA Binding'].values)

#%% create multilayer projector

class deepProjectorDecider(Model):
    def __init__(self, projDim, inputDim, intermedDim):
        super(deepProjectorDecider, self).__init__()
        self.projDim = projDim
        self.inputDim = inputDim
        self.intermedDim = intermedDim
        self.projector = tf.keras.Sequential([
            tf.keras.layers.InputLayer(input_shape = (self.inputDim)),
            tf.keras.layers.Dense(self.intermedDim),
            tf.keras.layers.Dense(self.projDim)])
        self.decider = tf.keras.Sequential([
            tf.keras.layers.InputLayer(input_shape = (self.projDim,)),
            tf.keras.layers.Dense(self.intermedDim),
            tf.keras.layers.Dense(2)])
    def call(self, x):
        projected = self.projector(x)
        decided = self.decider(projected)
        return decided

pdModelAntDeep = deepProjectorDecider(1, 2300, 1000)
targetsAntDeep = emi_binding['ANT Binding'].values
lossFn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True)
pdModelAntDeep.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
pdModelAntDeep.fit(features, targetsAnt, 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)

pdModelPsyDeep = deepProjectorDecider(1, 2300, 2500)
pdModelPsyDeep.compile(optimizer = 'adam', loss = lossFn, metrics = ['accuracy'])
targetsPsyDeep = emi_binding['OVA Binding'].values
pdModelPsyDeep.fit(features, targetsPsy, 
                        batch_size = batch_sz, 
                        epochs = nepochs,
                        verbose = 1)

projIsoAntDeep = pdModelAntDeep.projector(iso_onehot.values)
plt.figure()
plt.scatter(projIsoAntDeep, iso_binding['ANT Binding'].values)
plt.xlabel('Deep NN Projection')
plt.ylabel('Measured ANT binding')
antCorrDeep = sc.stats.spearmanr(projIsoAntDeep, iso_binding['ANT Binding'].values)
print(f'antigen spearman {antCorrDeep[0]} p = {antCorrDeep[1]}')

projIsoPsyDeep = pdModelPsyDeep.projector(iso_onehot.values)
plt.figure()
plt.scatter(projIsoPsyDeep, iso_binding['OVA Binding'].values)
plt.xlabel('Deep NN Projection')
plt.ylabel('Measured OVA binding')
ovaCorrDeep = sc.stats.spearmanr(projIsoPsyDeep, iso_binding['OVA Binding'].values)
print(f'ova spearman {ovaCorrDeep[0]} p = {ovaCorrDeep[1]}')
