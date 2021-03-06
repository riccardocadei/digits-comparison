import torch

from models import *
from training import *
import time
#import pandas as pd


def main():
    '''
    Run all the experiments once
    '''
    exp_data = {"model": [],
                "number_parameters": [],
                "use_auxiliary_loss":[],
                "learning_rate": [],
                "use_augmentation":[],
                "weight_decay" :[],
                "num_experiments":[],
                "mean_train_errors": [],
                "std_train_errors": [],
                "mean_val_errors": [],
                "std_val_errors": [],
                "mean_test_errors" :[],
                "std_test_errors" :[],
                }

    models = [MLP, ConvNet, ResNet, DeepConvNet, DeepConvNet, Siamese, Siamese] 
    model_names = ["MLP", "ConvNet", "ResNet", "DeepConvNet", "DeepConvNet", "Siamese", "Siamese"] 

    model_params = [[2], # MLP 2 classes
                [2], # ConvNet 2 classes
                [10, 2, 2, 128], # Resnet depth 10, 2 classes, 2 input channels, 128 channels in ConvBlocks
                [False], # DeepConvNet without aux loss
                [True], # DeepConvNet with aux loss
                [False], # Siamese without aux loss
                [True]] # Siamese with aux loss


    weight_decays = {"MLP": 1e-1,
                 "ConvNet": 1e-1,
                 "ResNet": 1e-1,
                 "DeepConvNet" : 1e-3,
                 "Siamese": 1e-3}

    learning_rates = {"MLP": 1e-4,
                 "ConvNet": 1e-4,
                 "ResNet": 1e-4,
                 "DeepConvNet" : 1e-3,
                 "Siamese": 1e-3}

    use_augment = [False, True] 
    epochs = [25, 200] # 25 epochs without augmentation, 200 epochs with augmentation
    num_experiments = [1, 1] # 10 experiments for each model without augmentation, 10 for each model with augmentation

    total_experiments = 14
    i = 0
    for augment, nb_epochs, n_experiment in zip(use_augment, epochs, num_experiments):
        for model, model_name, params in zip(models, model_names, model_params):

            lr = learning_rates[model_name]
            weight_decay = weight_decays[model_name]
            use_aux_loss = (model_name == "Siamese" or model_name == "DeepConvNet") and params[0] == True
            num_model_params = count_parameters(model(*params))

            i+=1
            print("\nExperiment: ({}/{})".format(i, total_experiments))
            print("Model:", model_name, " Number of Parameters:", num_model_params)
            print("Augmentations:", augment, " Epochs:", nb_epochs, " Use Auxiliary Loss:", use_aux_loss)

            # saving experiment setup
            exp_data["model"].append(model_name)
            exp_data["number_parameters"].append(num_model_params)
            exp_data["use_auxiliary_loss"].append(use_aux_loss)
            exp_data["learning_rate"].append(lr)
            exp_data["use_augmentation"].append(augment)
            exp_data["weight_decay"].append(weight_decay)
            exp_data["num_experiments"].append(n_experiment)

            # run experiment
            ((mean_train_error,std_train_error), 
                (mean_val_error,std_val_error), 
                (mean_test_error,std_test_error)) = evaluate_model(model,
                                                             *params, 
                                                            n_experiments = n_experiment,
                                                            use_auxiliary_loss = use_aux_loss,
                                                            aux_loss_weight=0.15, 
                                                            model_name=model_name,
                                                            nb_epochs = nb_epochs, 
                                                            weight_decay = weight_decay,
                                                            augment=augment,
                                                            batch_size = 50,
                                                            lr = lr, 
                                                            percentage_val=0.1,
                                                            verbose=0)
            print('Training Set: \n- Error: {}'.format(mean_train_error) )
            print('Validation Set: \n- Error: {}'.format(mean_val_error))
            print('Test Set: \n- Error: {}'.format(mean_test_error))

            # saving experiment results
            exp_data["mean_train_errors"].append(mean_train_error.numpy())
            exp_data["std_train_errors"].append(std_train_error.numpy())
            exp_data["mean_val_errors"].append(mean_val_error.numpy())
            exp_data["std_val_errors"].append(std_val_error.numpy())
            exp_data["mean_test_errors"].append(mean_test_error.numpy())
            exp_data["std_test_errors"].append(std_test_error.numpy())


    #df = pd.DataFrame(data=exp_data)
    #df.to_csv("experiments.csv", index=False)
    #print("Data updated on ./experiments.csv")
    #print(df.head())

    
if __name__ == '__main__':
    print("#"*100)
    print("\n>>> NOTE: total time for running all the experiments on Google Colab GPU is: 1 hour 40 minutes")
    print()
    print("#"*100)
    start = time.time()
    main()
    end = time.time()
    print("Elapsed time in seconds:", end-start)

            

