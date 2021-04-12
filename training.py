import torch
from torch import nn
from torch import optim
from torch.nn import functional as F
import math
from datetime import datetime
from torch.nn.modules.loss import _Loss
from torch import Tensor

import dlc_practical_prologue as prologue
from other import *


# returns a split in train and validation data
def random_split(train_input, train_target, train_classes, percentage_val=0.1):
    # shuffle data
    idx = torch.randperm(train_input.size(0))
    train_input = train_input[idx]
    train_target = train_target[idx]
    train_classes = train_classes[idx]
    # split 
    train_size = math.floor(train_input.size(0) * (1 - percentage_val))
    val_size = train_input.size(0) - train_size
    train_input, val_input = torch.split(train_input, [train_size, val_size])
    train_target, val_target = torch.split(train_target, [train_size, val_size])
    train_classes, val_classes = torch.split(train_classes, [train_size, val_size])
    return train_input, train_target, train_classes, val_input, val_target, val_classes

# since our task is to predict whether the first channel of images in train_input
# is lesser or equal than the second channel, we can flip the two channels and double our
# dataset size
def augment(train_input, train_target, train_classes):
    flipped_input = torch.empty(train_input.size())
    flipped_target = torch.empty(train_target.size())
    flipped_classes = torch.empty(train_classes.size())

    flipped_input[:,0] = train_input[:, 1].clone()
    flipped_input[:,1] = train_input[:, 0].clone()

    flipped_target = ((train_classes[:,1]-train_classes[:,0])<=0).int()

    flipped_classes[:,0] = train_classes[:,1].clone()
    flipped_classes[:,1] = train_classes[:,0].clone()
    augmented_input = torch.cat((train_input, flipped_input), dim=0)
    augmented_target = torch.cat((train_target, flipped_target), dim=0)
    augmented_classes = torch.cat((train_classes, flipped_classes), dim=0)
    return augmented_input, augmented_target, augmented_classes


class AuxiliaryLoss(_Loss):
    def __init__(self, reduction='mean', weight_classification=0.2 , weight_inequality=0.6):
        super().__init__(reduction=reduction)
        self.reduction = reduction
        tot = weight_classification * 2 + weight_inequality
        if  tot != 1.0:
            raise ValueError("2 * weight classification + weight of inequality must be 1!But you gave:", tot)
        self.weight_classification = weight_classification
        self.weight_inequality = weight_inequality

    # preds is of size: (N, 2 (inequality) + 10 (class1) + 10 (class2))
    # target is of size: (N, 1 (inequality) + 1 (class1) + 1 (class2))
    def forward(self, preds: Tensor, target: Tensor):
        loss_ineq = F.cross_entropy(preds[:, :2], target[:,0])
        loss_class1 = F.cross_entropy(preds[:, 2:12], target[:, 1])
        loss_class2 = F.cross_entropy(preds[:, 12:22], target[:, 2])
        loss = self.weight_classification * (loss_class1 + loss_class2) + self.weight_inequality * loss_ineq
        return loss.mean()



def build_target(train_target, train_classes, use_auxiliary_loss):
    if not use_auxiliary_loss:
        return train_target
    else:
        target = torch.empty(train_target.size(0), 3)
        target[:, 0] = train_target
        target[:, 1:] = train_classes
        return target.long()


def get_criterion(use_auxiliary_loss, weight_classification=0.2, weight_inequality=0.6):
    if not use_auxiliary_loss:
        return nn.CrossEntropyLoss()
    else:
        return AuxiliaryLoss(weight_classification=weight_classification,
                                         weight_inequality=weight_inequality)
        


def run_experiment(model, use_auxiliary_loss, nb_epochs = 25, weight_decay = 0.1, model_name="model", period=1,
                            mini_batch_size = 50, lr = 1e-3*0.5, percentage_val=0.1, verbose=1, plot=True):

    # device
    device = ('cuda' if torch.cuda.is_available() else 'cpu')
    if verbose>=1: print("Device used: ", device)

    # loading the data
    N = 1000 
    (train_input, train_target, train_classes,
     test_input, test_target, test_classes) = prologue.generate_pair_sets(N)
    if verbose>=1: print("Loading training and test set...")
    # splitting the dataset and data augmentation
    (train_input, train_target, train_classes, val_input, val_target, val_classes) = random_split(train_input, train_target, train_classes, percentage_val)

    if verbose>=1: print("Splitting the training set in training and validation set...")
    train_input, train_target, train_classes = augment(train_input, train_target, train_classes)
    if verbose>=1: print("Data augmentation...")
    if verbose>=1: print("In total there are: \n - {} samples in the Training Set ({} *2), \n - {} samples in the Validation Set, \n - {} samples in the Test Set"
        .format(train_input.size(0), int((1-percentage_val)*N), int(percentage_val*N), N))

    if verbose>=1: print('Number of parameters of the model: {}'.format(count_parameters(model)))

    train_target = build_target(train_target, train_classes, use_auxiliary_loss)
    val_target = build_target(val_target, val_classes, use_auxiliary_loss)

    # move to Device
    model = model.to(device)
    train_input = train_input.to(device)
    train_target = train_target.to(device)
    val_input = val_input.to(device)
    val_target = val_target.to(device)
    test_input = test_input.to(device)
    test_target = test_target.to(device)
    
    # training
    criterion = get_criterion(use_auxiliary_loss)
    optimizer = optim.Adam(model.parameters(), lr = lr, weight_decay=weight_decay)
    if verbose>=1: print('Training...')
    start = datetime.now()
    train_losses, val_losses = train(model, train_input, train_target, val_input, val_target, optimizer, criterion, model_name=model_name,
                                        nb_epochs=nb_epochs,  mini_batch_size=mini_batch_size, verbose=verbose)
    end = datetime.now()
    if verbose >= 1: print('Training time: {0:.3f} seconds'.format((end-start).microseconds/1000000))
    path = "./model_weights/" + model_name + ".pth"
    if verbose >= 1: print("Saved the model weights in: ", path)

    # load weights of best model in validation
    model.load_state_dict(torch.load(path))

    # evaluate the performances
    train_error = test(model, train_input, train_target[:,0], device)
    if verbose>=1: print('\nTraining error: {0:.3f} %'.format(train_error*100) )
    val_error = test(model, val_input, val_target[:,0], device)
    if verbose>=1: print('Validation error: {0:.3f} %'.format(val_error*100) )
    test_error = test(model, test_input, test_target, device)
    if verbose>=1: print('Test error: {0:.3f} %'.format(test_error*100) )

    if plot==True: plot_train_val(train_losses, val_losses, period=period, model_name=model_name)

    return train_losses, val_losses, (train_error, val_error, test_error)





def train(model, train_input, train_target, val_input, val_target, 
                 optimizer, criterion, model_name="model", nb_epochs = 25, mini_batch_size=50, verbose=2):
    """
    Train model
    """
    train_losses = []
    val_losses = []
    for epoch in range(nb_epochs):
        train_loss_e = 0
        num_batches = 0
        model.train()
        # train batch
        for b in range(0, train_input.size(0), mini_batch_size):
            # Forward step
            output = model(train_input.narrow(0, b, mini_batch_size))
            # Compute the Loss
            loss = criterion(output, train_target.narrow(0, b, mini_batch_size))

            # Backward step
            model.zero_grad()
            loss.backward()
            # Update the Gradient
            optimizer.step()
            # Collect the Losses
            train_loss_e += loss.data.item()
            num_batches += 1
        train_loss = train_loss_e / num_batches
        train_losses.append(train_loss)

        model.eval()
        # validation
        val_preds = model(val_input)
        val_loss = criterion(val_preds, val_target).data.item()
        val_losses.append(val_loss)
        # save best model in validation
        if val_loss <= min(val_losses):
            torch.save(model.state_dict(), "./model_weights/" + model_name + ".pth")

        if verbose==2:
            print("Epoch", epoch+1, "/", nb_epochs, "train loss:", train_loss, "valid loss:", val_loss)

    return train_losses, val_losses


def evaluate_model(model, n, nb_epochs = 25, weight_decay = 0.1, 
                    mini_batch_size = 50, lr = 1e-3*0.5, percentage_val=0.1, verbose=0):
    train_errors = []
    val_errors = []
    test_errors = []
    print('Number of experiments: {}'.format(n))
    print('Computing...')
    for i in range(n):
        _, _, errors = run_experiment(model, nb_epochs=nb_epochs, percentage_val=percentage_val, mini_batch_size=mini_batch_size, weight_decay=weight_decay, lr=lr, verbose=verbose, plot=False);
        train_errors.append(errors[0])
        val_errors.append(errors[1])
        test_errors.append(errors[2])
    mean_train_error = torch.mean(torch.Tensor(train_errors))
    mean_val_error = torch.mean(torch.Tensor(val_errors))
    mean_test_error = torch.mean(torch.Tensor(test_errors))
    std_train_error = torch.std(torch.Tensor(train_errors))
    std_val_error = torch.std(torch.Tensor(val_errors))
    std_test_error = torch.std(torch.Tensor(test_errors))
    print('Training Set: \n- Mean: {0:.3f}\n- Standard Error: {0:.3f}'.format(mean_train_error,std_train_error) )
    print('Validation Set: \n- Mean: {0:.3f}\n- Standard Error: {0:.3f}'.format(mean_val_error,std_val_error) )
    print('Test Set: \n- Mean: {0:.3f}\n- Standard Error: {0:.3f}'.format(mean_test_error,std_test_error) )
    return

def test(model, test_input, test_target, device):
    model.eval()
    preds = torch.empty(test_target.size(0), 2).to(device)
    # avoid memory overflow
    batch_size = 20
    for i in range(0, test_input.size(0), batch_size):
      inputs = test_input.narrow(0, i, batch_size)
      with torch.no_grad():
         # select only the first two columns in case auxiliary loss is used in training
        outputs = model(inputs)[:, 0:2]
      preds[i : i + batch_size, :] = outputs
        
    _, predicted_classes = preds.max(1)
    test_error = (predicted_classes-test_target).abs().sum() / test_target.size(0)
    return test_error
    

