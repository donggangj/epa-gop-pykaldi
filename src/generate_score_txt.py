import os
import glob
from pathlib import Path

import torchaudio
import torch
import torch.optim as optim

from finetuning_utils import *
from utils import *
from dataset import *

from pytorch_models import *

from IPython import embed

import argparse

def removeSymbols(str, symbols):
    for symbol in symbols:
        str = str.replace(symbol,'')
    return str

def get_alignments(alignments_path):
    alignments_dict = {}

    for l in open(alignments_path, 'r').readlines():
        l=l.split()
        #Get phones alignments
        if len(l) > 3 and l[1] == 'phones':
            logid = l[0]
            alignment = []
            alignments_dict[logid] = {}
            for i in range(2, len(l),3):
                current_phone =     removeSymbols(l[i],  ['[',']',',',')','(','\''])
                start_time    = int(removeSymbols(l[i+1],['[',']',',',')','(','\'']))
                duration      = int(removeSymbols(l[i+2],['[',']',',',')','(','\'']))
                end_time      = start_time + duration
                alignment.append((current_phone, start_time, end_time))
            alignments_dict[logid] = alignment
    return alignments_dict


def generate_scores_for_sample(phone_times, frame_level_scores):
    scores = []
    #Iterate over phone transcription and calculate score for each phome
    for phone_name, start_time, end_time in phone_times:
        #Do not score SIL phones
        if phone_name == 'SIL':
            continue

        #Check if the phone was uttered
        if start_time != end_time:
            current_phone_score = get_phone_score_from_frame_scores(frame_level_scores, 
                                                                    start_time, end_time, 'mean')
        #Use fixed negative score for deletions
        else:
            current_phone_score = -1000
        scores.append(phone_name, current_phone_score)
    return scores

def generate_scores_for_testset(model, testloader):
    print('Generating scores for testset')
    scores = []
    for i, batch in enumerate(testloader, 0):       
        print('Batch ' + str(i+1) + '/' + str(len(testloader)))
        logids      = unpack_logids_from_batch(batch)
        features    = unpack_features_from_batch(batch)
        labels      = unpack_labels_from_batch(batch)
        phone_times = unpack_phone_times_from_batch(batch)
        outputs     = (-1) * model(features)
        batch_size  = len(logids)

        frame_level_scores = get_scores_for_canonic_phones(outputs, labels)
        for i in range(batch_size):
            current_sample_scores = generate_scores_for_sample(phone_times[i], frame_level_scores[i])
            scores.append(current_sample_scores)
    return scores

def log_sample_scores_to_txt(scores, score_log_fh, phone_dict):
    for phone, score in scores:
        phone_number = phone_dict[phone_name] + 3
        score_log_fh.write( '[ ' + str(phone_number) + ' ' + str(score)  + ' ] ')

def log_testset_scores_to_txt(scores, score_log_fh, phone_dict):
    print('Writing scores to .txt')
    for sample_score in scores:
        log_sample_scores_to_txt(sample_score, score_log_fh, phone_dict)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dict-dir', dest='state_dict_dir', help='Directory to saved state dicts in .pth', default=None)
    parser.add_argument('--model-name', dest='model_name', help='Model name (usually the name of the wandb run that generated the .pth file)', default=None)
    parser.add_argument('--epa-root', dest='epa_root_path', help='EpaDB root directory', default=None)
    parser.add_argument('--sample-list', dest='sample_list_path', help='Path to list of samples to test on', default=None)
    parser.add_argument('--phone-list', dest='phone_list_path', help='Path to phone list', default=None)
    parser.add_argument('--labels-dir', dest='labels_dir', help='Directory where labels are found', default=None)     
    parser.add_argument('--gop-txt-dir', dest='gop_txt_dir', help='Directory to save generated scores', default=None)
    parser.add_argument('--features-path', dest='features_path', help='Path to features directory', default=None)
    parser.add_argument('--conf-path', dest='conf_path', help='Path to config directory used in feature extraction', default=None)
    parser.add_argument('--device', dest='device_name', help='Device name to use, such as cpu or cuda', default=None)
    parser.add_argument('--batchnorm', dest='batchnorm', help='Batchnorm mode', default=None)
    args = parser.parse_args()

    state_dict_dir      = args.state_dict_dir
    model_name          = args.model_name
    epa_root_path       = args.epa_root_path
    sample_list         = args.sample_list_path
    phone_list_path     = args.phone_list_path
    labels_dir          = args.labels_dir
    gop_txt_dir         = args.gop_txt_dir
    features_path       = args.features_path
    conf_path           = args.conf_path
    alignments_path     = args.alignments_path
    device_name         = args.device_name

    testset = EpaDB(epa_root_path, sample_list, phone_list_path, labels_dir, features_path, conf_path)
    testloader = torch.utils.data.DataLoader(testset, batch_size=16,
                                          shuffle=False, num_workers=0, collate_fn=collate_fn_padd)

    phone_count = testset.phone_count()

    #Get acoustic model to test
    model = FTDNN(out_dim=phone_count, device_name=device_name, batchnorm=args.batchnorm)
    model.eval()
    state_dict = torch.load(state_dict_dir + '/' + model_name + '.pth')
    model.load_state_dict(state_dict['model_state_dict'])

    phone_dict = testset._pure_phone_dict

    scores = generate_scores_for_testset(model, testloader)
    score_log_fh = open(gop_txt_dir+ '/' +'gop-'+model_name+'.txt', 'w+')
    log_testset_scores_to_txt(scores, score_log_fh, phone_dict)

if __name__ == '__main__':
    main()
