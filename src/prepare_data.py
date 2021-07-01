import glob
import os
import argparse
from FeatureManager import FeatureManager

def generate_arguments(args_dict):
    res = ""
    for arg_name, value in args_dict.items():
        res = res + "--" + arg_name + " " + str(value) + " "
    return res

def download_librispeech_models(librispeech_models_path):
    if not os.path.exists(librispeech_models_path):
        os.makedirs("librispeech_models/")
        os.system("wget https://kaldi-asr.org/models/13/0013_librispeech_v1_chain.tar.gz")
        os.system("wget https://kaldi-asr.org/models/13/0013_librispeech_v1_lm.tar.gz")
        os.system("wget https://kaldi-asr.org/models/13/0013_librispeech_v1_extractor.tar.gz")
        os.system("tar -xf 0013_librispeech_v1_chain.tar.gz -C " + librispeech_models_path)
        os.system("tar -xf 0013_librispeech_v1_lm.tar.gz -C " + librispeech_models_path)
        os.system("tar -xf 0013_librispeech_v1_extractor.tar.gz -C " + librispeech_models_path)
        os.system("rm -f 0013_librispeech_v1_chain.tar.gz")
        os.system("rm -f 0013_librispeech_v1_lm.tar.gz")
        os.system("rm -f 0013_librispeech_v1_extractor.tar.gz")

def prepare_pytorch_models(libri_chain_mdl_path, libri_chain_txt_path, acoustic_model_path, finetune_model_path, phone_count):
    #Convert librispeech acoustic model .mdl to .txt
    if not os.path.exists(libri_chain_txt_path):
        os.system("nnet3-copy --binary=false " + libri_chain_mdl_path + " " + libri_chain_txt_path)

    #Convert final.txt to pytorch acoustic model used in alginments stage
    if not os.path.exists(acoustic_model_path):
        args_dict = {"chain-model-path": libri_chain_txt_path,
                     "output-path":      acoustic_model_path}
        arguments = generate_arguments(args_dict)
        os.system("python src/convert_chain_to_pytorch.py " + arguments)

    #Generate model to finetune in training stage
    if not os.path.exists(finetune_model_path):
        args_dict = {"chain-model-path": libri_chain_txt_path,
                     "output-path":      finetune_model_path,
                     "phone-count":      phone_count}
        arguments = generate_arguments(args_dict)
        os.system("python src/convert_chain_to_pytorch_for_finetuning.py " + arguments)



def create_ref_labels_symlinks(epadb_root_path, labels_path):
    #Create symbolic links to epa reference labels
    for file in sorted(glob.glob(epadb_root_path + '*/labels/*')):
        fullpath = os.path.abspath(file)
        basename = os.path.basename(file)
        #Get spkr id
        spkr = fullpath.split('/')[-3]
        labels_dir_for_spkr = labels_path + spkr+ '/labels/' 
        #Create directory for speaker's labels
        if not os.path.exists(labels_dir_for_spkr):
            os.system('mkdir -p ' + labels_dir_for_spkr)
        #Make symbolic link to speaker labels from EpaDB directory
        if not os.path.exists(labels_dir_for_spkr + '/' + basename):
            os.system('ln -s ' + fullpath + ' ' + labels_dir_for_spkr + '/')

    #Handle symbolic links for EpaDB reference transcriptions
    if not os.path.exists(labels_path + '/reference_transcriptions.txt'):
        current_path = os.getcwd()
        cmd = 'ln -s ' + current_path + "" + epadb_root_path + '/reference_transcriptions.txt ' + current_path + "/" + args.labels_path + '/reference_transcriptions.txt'
        print(cmd)
        os.system(cmd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--epa-root-path', dest='epa_root_path', help='EpaDB root path', default=None)
    parser.add_argument('--features-path', dest='features_path', help='Path to features directory', default=None)
    parser.add_argument('--conf-path', dest='conf_path', help='Path to config directory used in feature extraction', default=None)
    parser.add_argument('--labels-path', dest='labels_path', help='Path to create symlinks to EpaDB ref labels', default=None)
    parser.add_argument('--librispeech-models-path', dest='librispeech_models_path', help='Path to directory where Librispeech models will be found', default=None)
    parser.add_argument('--libri-chain-mdl-path', dest='libri_chain_mdl_path', help='Path to Librispeech chain acoustic model .mdl', default=None)
    parser.add_argument('--libri-chain-txt-path', dest='libri_chain_txt_path', help='Path where .txt version of final.mdl will be created', default=None)
    parser.add_argument('--acoustic-model-path', dest='acoustic_model_path', help='Path where Pytorch acoustic model will be created', default=None)
    parser.add_argument('--finetune-model-path', dest='finetune_model_path', help='Path where the model to finetune will be created', default=None)
    parser.add_argument('--phone-count', dest='phone_count', help='Size of the phone set for the current system', default=None)

    args = parser.parse_args()

    features_path = args.features_path
    conf_path = args.conf_path
    epadb_root_path = args.epa_root_path

    #Download librispeech models and extract them into librispeech-models-path
    download_librispeech_models(args.librispeech_models_path)

    #Prepare pytorch models
    prepare_pytorch_models(args.libri_chain_mdl_path, args.libri_chain_txt_path, args.acoustic_model_path,
                           args.finetune_model_path, args.phone_count)

    #Extract features
    feature_manager = FeatureManager(epadb_root_path, features_path, conf_path)
    feature_manager.extract_features_using_kaldi()

    #Create symlinks
    create_ref_labels_symlinks(epadb_root_path, args.labels_path)


