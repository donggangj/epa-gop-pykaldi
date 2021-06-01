import os, errno, re
import os.path as path
from os import remove
import numpy as np
import textgrids # pip install git+https://github.com/Legisign/Praat-textgrids
from scipy.stats.stats import pearsonr
from IPython import embed
import pandas as pd
import joblib
import shutil
import argparse
import glob

def phonelist2str(phones):
    return " ".join(["%3s"%p for p in phones])

def mkdirs(newdir):
    try: os.makedirs(newdir)
    except OSError as err:
        # Raise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not os.path.isdir(newdir):
            raise


# Generates transcription file without allophonic variations

def generate_trans_SAE(trans_complete):

    complete_text = open(trans_complete)
    pruned_text = open("transcriptionsSAE.txt","w")

    d = [('Th/', ''), ('Kh/', ''), ('Ph/', ''), ('AX', 'AH0'), ('/DX', '')]

    s = complete_text.read()
    for i,o in d:
        s = s.replace(i,o)
    pruned_text.write(s)

    complete_text.close()
    pruned_text.close()

    return pruned_text


# Function that reads transcriptions files and loads them to
# a series of useful dictionaries

def generate_dict_from_transcripctions(transcriptions):

    trans_dict = dict()
    trans_dict_clean = dict()
    sent_dict = dict()

    # Read transcription file
    for line in open(transcriptions,'r'):

        fields = line.strip().split()

        if len(fields) <= 2:
            continue

        sent = fields[1].strip(":")

        if fields[0] == "TEXT":
            sent_dict[sent] = fields[2:]

        if fields[0] != "TRANSCRIPTION":
            continue

        if sent not in trans_dict_clean:

            # Before loading the first transcription for a sentence,
            # create an entry for it in the dict. The entry will be a
            # list of lists. One list for each possible transcription
            # for that sentence.

            trans_dict[sent] = list()
            trans_dict_clean[sent] = list()

        trans = [[]]
        for i in range(2, len(fields)):
            phones = fields[i].split("/")

            # Reproduce the transcriptions up to now as many times as
            # the number of phone variations in this slot. Then, append
            # one variation to each copy.

            trans_new = []
            for p in phones:
                for t in trans:
                    t_tmp = t + [p.strip()]
                    trans_new.append(t_tmp)
            trans = trans_new

        trans_dict[sent] += trans

    for sent, trans in trans_dict.items():
        trans_clean_new = []
        for t in trans:
            trans_clean_new.append([x for x in t if x != '0'])

        if sent not in trans_dict_clean:
            trans_dict_clean[sent] = list()

        trans_dict_clean[sent] += trans_clean_new

    return trans_dict, trans_dict_clean, sent_dict


# Function that reads the output from pykaldi aligner and returns the
# phone alignments

def get_kaldi_alignments(path_filename):

    output = []
    unwanted_characters = '[\[\]()\'\",]'
    print(path_filename)
    for line in open(path_filename).readlines():
        l=line.split()

        if 'phones' == l[1]:
            print(l)
            logid = l[0]
            data = l[2:]
            i = 0
            phones_name = []
            while i < len(data):
                phone_name = re.sub(unwanted_characters, '', data[i])
                #Turn phone into pure phone (i.e. remove _context)
                if '_' in phone_name:
                    phone_name = phone_name[:-2]
                if '0' in phone_name or '1' in phone_name:
                    phone_name = phone_name[:-1]
                print(phone_name)
                phones_name.append(phone_name)
                i = i + 3

            output.append({'logid': str(logid),
                           'phones_name':phones_name})

    df_phones = pd.DataFrame(output).set_index("logid")

    return df_phones


def get_reference(file):
    reference = []
    annot_manual = []
    labels = []
    start_times = []
    end_times = []
    
    i = 0
    for line in open(file).readlines():
        l=line.split()
        reference.append(l[1])
        annot_manual.append(l[2])
        labels.append(l[3])
        start_times.append(l[4])
        end_times.append(l[5])



        i += 1

    return reference, annot_manual, labels, start_times, end_times

def remove_deletion_labels_and_times(trans_zero, trans_reff_complete, labels, start_times, end_times):
    clean_labels = []
    clean_trans_reff = []
    clean_start_times = []
    clean_end_times = []
    for i, phone in enumerate(trans_zero):
        if phone != '0':
            clean_labels.append(labels[i])
            clean_trans_reff.append(trans_reff_complete[i])
            clean_start_times.append(start_times[i])
            clean_end_times.append(end_times[i])

    return clean_labels, clean_trans_reff, clean_start_times, clean_end_times

def remove_0_canonic_phone(trans_reff_complete, annot_kaldi, labels, start_times, end_times):
    clean_trans_reff = []
    clean_annot_kaldi = []
    clean_labels = []
    clean_start_times = []
    clean_end_times = []
    for i, phone in enumerate(trans_reff_complete):
        if phone != '0':
            clean_trans_reff.append(phone)
            clean_annot_kaldi.append(annot_kaldi[i])
            clean_labels.append(labels[i])
            clean_start_times.append(start_times[i])
            clean_end_times.append(end_times[i])

    return clean_trans_reff, clean_annot_kaldi, clean_labels,  clean_start_times, clean_end_times


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--transcription-file', dest='transcriptions', help='File with reference phonetic transcriptions of each of the phrases', default=None)
    parser.add_argument('--utterance-list', dest='utterance_list', help='File with utt list', default=None)
    parser.add_argument('--reference-file', dest='reference_path', help='', default=None)
    parser.add_argument('--alignment-file', dest='align_path', help='', default=None)
    parser.add_argument('--output', dest='output_dir', help='Output directory for labels', default=None)


    args = parser.parse_args()

    # Code that generates a pickle with useful data to analyze.
    # The outpul will be used to compute ROCs, AUCs and EERs.

    output = []
    output_tmp  = []

    trans_dict_complete, trans_dict_clean_complete, sent_dict_complete = generate_dict_from_transcripctions(args.transcriptions)
    generate_trans_SAE(args.transcriptions)

    kaldi_alignments = get_kaldi_alignments(args.align_path)

    utterance_list = []
    utt_list_fh = open(args.utterance_list, 'r')
    for line in utt_list_fh.readlines():
        logid = line.split(' ')[0]
        utterance_list.append(logid)


    # Now, iterate over utterances
    for utterance in utterance_list:

        spk, sent = utterance.split("_")

        file = "%s/%s/%s/%s.txt"%(args.reference_path, spk, "labels", utterance) #Labels file for current utterance
        print("----------------------------------------------------------------------------------------")
        print("Speaker %s, sentence %s: %s (File: %s)"%(spk, sent, " ".join(sent_dict_complete[sent]), file))
        
        #Get phone list from manual annotation 
        trans_reff_complete, annot_manual, labels, start_times, end_times = get_reference(file)


        if utterance in kaldi_alignments.index.values:
            phones = kaldi_alignments.loc[utterance].phones_name
            annot_kaldi = []
            for phone in phones:
                if phone not in ['sil', '[key]', 'sp', '', 'SIL', '[KEY]', 'SP']:
                    if phone[-1] not in ['1', '0', '2']:
                        annot_kaldi += [phone]
                    else:
                        # If it has an int at the end, delete it, except for AH0

                        #annot_kaldi += [phone] if(phone == 'AH0') else [phone[:-1]]
                        #For the time being, remove AH0 aswell
                        annot_kaldi += [phone[:-1]]
        else:

            raise Exception("WARNING: Missing alignment for "+ utterance)



        # Find the transcription for this sentence that best matches the annotation

        best_trans = -1
        best_trans_corr = 0

        for trans_idx, trans in enumerate(trans_dict_clean_complete[sent]):
            if(len(trans) == len(annot_kaldi)):
                num_correct = np.sum([t==a for t, a in np.c_[trans,annot_kaldi]])
                if num_correct > best_trans_corr:
                    best_trans_corr = num_correct
                    best_trans = trans_idx


        if best_trans != -1:


            trans      = trans_dict_clean_complete[sent][best_trans]
            trans_zero = trans_dict_complete[sent][best_trans]



            print("TRANS_REFF:           %s (chosen out of %d transcriptions)"%(phonelist2str(trans), len(trans_dict_clean_complete[sent])))
            print("TRANS_KALDI:          "+phonelist2str(annot_kaldi))
            print("LABEL:                "+phonelist2str(labels))
            print("TRANS_ZERO:           "+phonelist2str(trans_zero))
            print("TRANS_MANUAL:         "+phonelist2str(annot_manual))
            print("TRANS_REFF_COMPLETE:  "+phonelist2str(trans_reff_complete))
            print("TRANS_WITHOUT_ZERO:   "+phonelist2str(trans))

            if len(labels) > len(annot_kaldi):
                labels, trans_reff_complete, start_times, end_times = remove_deletion_labels_and_times(trans_zero, trans_reff_complete, labels, start_times, end_times)
            if len(labels) < len(annot_kaldi):
                #annot_kaldi = remove_non_labeled_phones_from_kaldi_annotation(annot_kaldi, annot_manual)  
                raise Exception('Kaldi annotaton is longer than manual annotation. Logid: ' + utterance)

            if '0' in trans_reff_complete:
                trans_reff_complete, annot_kaldi, labels, start_times, end_times = remove_0_canonic_phone(trans_reff_complete, annot_kaldi, labels, start_times, end_times)
            
            outdir  = "%s/labels_with_kaldi_phones/%s" % (args.output_dir, spk)
            outfile = "%s/%s.txt" % (outdir, utterance)
            mkdirs(outdir)
            np.savetxt(outfile, np.c_[np.arange(len(annot_kaldi)), trans_reff_complete, annot_kaldi, labels, start_times, end_times], fmt=utterance+"_%s %s %s %s %s %s")


        else:

            print(trans_dict_clean_complete[sent])
            print(phones)
            print(annot_kaldi)
            raise Exception("WARNING: %s does not match with transcription"%(spk))



