import os
import glob
from pathlib import Path

import torchaudio
import torch
import torch.optim as optim

from utils import *
from dataset import *

from pytorch_models import *

import wandb

def unpack_features_from_batch(batch):
    return torch.stack([features for features, _,_,_,_ in batch])

def unpack_labels_from_batch(batch):
    return torch.stack([labels for _,_,_,_,labels in batch])

def collate_fn_padd(batch):
    '''
    Padds batch of variable length (both features and labels)
    '''
    ## padd
    batch_features = [ features for features, _,_,_,_ in batch ]
    batch_features = torch.nn.utils.rnn.pad_sequence(batch_features, batch_first=True)
    batch_labels = [ labels for _,_,_,_, labels in batch ]
    batch_labels = torch.nn.utils.rnn.pad_sequence(batch_labels, batch_first=True)
    batch = [(batch_features[i], batch[i][1], batch[i][2], batch[i][3], batch_labels[i]) for i in range(len(batch))]
    return batch

#The model outputs a score for each phone in each frame. This function extracts only the relevant scores,
#i.e the scores for the canonic phone in each frame based on the labels that come from the annotations.
#Scores and labels for all samples in the batch are returned one after the other in the same vector.
def get_relevant_scores_and_labels(outputs, labels):
    #Generate mask based on non-zero labels
    outputs_mask = torch.abs(labels)
    #Mask outputs and sum over phones to get a single value for the relevant phone in each frame
    outputs = outputs * outputs_mask
    outputs = torch.sum(outputs, dim=2)
    #Sum over phones to keep relevant label for each frame
    labels = torch.sum(labels, dim=2)
    #Remove labels == 0 (silence frames) in both labels and outputs
    outputs = outputs[labels != 0]
    labels = labels[labels != 0]
    return outputs, labels

def criterion(batch_outputs, batch_labels):
    '''
    Calculates loss
    '''
    loss_fn = torch.nn.BCEWithLogitsLoss()
    batch_outputs, batch_labels = get_relevant_scores_and_labels(batch_outputs, batch_labels)
    #Calculate loss
    loss = loss_fn(batch_outputs, batch_labels)
    return loss

def train(model, trainloader, testloader):

    #Freeze all layers except the last
    for name, param in model.named_parameters():
        if 'layer19' not in name:
            param.requires_grad = False

    optimizer = optim.SGD(model.parameters(), lr=0.001, momentum=0.9)

    running_loss_log_fh = open('running_loss.log', "w+")

    for epoch in range(2):  # loop over the dataset multiple times

        running_loss = 0.0
        for i, data in enumerate(trainloader, 0):            
            #print("Batch " + str(i))
            # get the inputs; data is a list of (features, transcript, speaker_id, utterance_id, labels)
            inputs = unpack_features_from_batch(data)
            batch_labels = unpack_labels_from_batch(data)


            # zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = model(inputs)

            #print(outputs.size())

            #Aca hay que ver que onda el criterion
            loss = criterion(outputs, batch_labels)
            loss.backward()
            optimizer.step()

            #print statistics
            running_loss += loss.item()

            if i % 20 == 19:    # print every 2000 mini-batches
                print('[%d, %5d] train_loss: %.3f' %
                      (epoch + 1, i + 1, running_loss / 20))
                wandb.log({"train_loss": running_loss/20})
                running_loss = 0.0
                
        test_loss = test(model, testloader)
        wandb.log({"test_loss": test_loss})

    running_loss_log_fh.close()

    print('Finished Training')

    PATH = './test.pth'
    torch.save(model.state_dict(), PATH)

    return model




def test(model, testloader):

    dataiter = iter(testloader)
    batch = dataiter.next()
    features = unpack_features_from_batch(batch)
    labels = unpack_labels_from_batch(batch)

    outputs = model(features)

    loss = criterion(outputs, labels)

    loss = loss.item()

    return loss

def main():
    wandb.init(project="gop-finetuning")

    trainset = EpaDB('.', 'epadb_test_path_list', 'phones_epa.txt')

    testset = EpaDB('.', 'epadb_test_path_list', 'phones_epa.txt')

    trainloader = torch.utils.data.DataLoader(trainset, batch_size=2,
                                      shuffle=True, num_workers=1, collate_fn=collate_fn_padd)

    testloader = torch.utils.data.DataLoader(testset, batch_size=6,
                                          shuffle=False, num_workers=2, collate_fn=collate_fn_padd)

    phone_count = trainset.phone_count()

    #Get acoustic model to train
    model = FTDNN(out_dim=phone_count)
    model.load_state_dict(torch.load('model_finetuning.pt'))

    wandb.watch(model, log_freq=100)
    model = train(model, trainloader, testloader)
    #test(model, testloader)

main()