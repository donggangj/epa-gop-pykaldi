import yaml
import argparse
import os
from utils import *
from IPython import embed
from evaluate_many_epochs import generate_scores_and_evaluate_epochs

def run_train(config_dict, device_name):
	if "held-out" in config_dict and config_dict["held-out"]:
		run_train_heldout(config_dict, device_name)
	else:
		run_train_kfold(config_dict, device_name)

def run_train_kfold(config_dict, device_name):
	fold_amount = config_dict["folds"]
	args_dict = {"utterance-list-path":       config_dict["utterance-list-path"], 
	             "folds":                     fold_amount,
	             "epadb-root-path":           config_dict["epadb-root-path"],
				 "train-sample-list-dir":     config_dict["train-sample-list-dir"],
				 "test-sample-list-dir":      config_dict["test-sample-list-dir"]
	            }
	run_script("src/generate_kfold_utt_lists.py", args_dict)


	for fold in range(fold_amount):
		args_dict = {"run-name": 			 	 config_dict["run-name"],
					 "trainset-list": 		 	 config_dict["train-sample-list-dir"] + 'train_sample_list_fold_' + str(fold),
 					 "testset-list": 		 	 config_dict["test-sample-list-dir"]  + 'test_sample_list_fold_'  + str(fold),
					 "fold": 				 	 fold,
	 				 "epochs": 				 	 config_dict["epochs"],
	 				 "swa-epochs":			 	 config_dict.get("swa-epochs", 0),	 				 
					 "layers": 		 		 	 config_dict["layers"],
					 "use-dropout": 		 	 config_dict["use-dropout"],
					 "dropout-p": 		     	 config_dict["dropout-p"],
					 "learning-rate":        	 config_dict["learning-rate"],
					 "scheduler":                config_dict.get("scheduler", "None"),
				     "swa-learning-rate":        config_dict.get("swa-learning-rate", 0),
 					 "batch-size":           	 config_dict["batch-size"],
					 "norm-per-phone-and-class": config_dict["norm-per-phone-and-class"],
	                 "use-clipping":         	 config_dict["use-clipping"],
	                 "batchnorm":            	 config_dict["batchnorm"],
					 "phones-file": 		 	 config_dict["phones-list-path"],
					 "labels-dir": 			 	 config_dict["labels-dir"],
					 "model-path": 			 	 config_dict["finetune-model-path"],
					 "phone-weights-path":   	 config_dict["phone-weights-path"],
					 "train-root-path": 		 config_dict["epadb-root-path"],
					 "test-root-path": 		     config_dict["epadb-root-path"],
					 "features-path": 		 	 config_dict["features-path"],
					 "conf-path": 			 	 config_dict["features-conf-path"],
					 "test-sample-list-dir": 	 config_dict["test-sample-list-dir"],
					 "state-dict-dir": 		 	 config_dict["state-dict-dir"],
					 "use-multi-process":    	 config_dict["use-multi-process"],
					 "device":               	 device_name				 
					}
		run_script("src/train.py", args_dict)

def run_train_heldout(config_dict, device_name):
	args_dict = {"run-name": 			 	 config_dict["run-name"],
				 "trainset-list": 		 	 config_dict["train-list-path"],
				 "testset-list": 		 	 config_dict["test-list-path"],
				 "fold": 				 	 0,
 				 "epochs": 				 	 config_dict["epochs"],
 				 "swa-epochs":			 	 config_dict.get("swa-epochs", 0),
				 "layers": 		 		 	 config_dict["layers"],
				 "use-dropout": 		 	 config_dict["use-dropout"],
				 "dropout-p": 		     	 config_dict["dropout-p"],
				 "learning-rate":        	 config_dict["learning-rate"],
				 "scheduler":                config_dict.get("scheduler", "None"),
				 "swa-learning-rate":        config_dict.get("swa-learning-rate", 0),
				 "batch-size":           	 config_dict["batch-size"],
				 "norm-per-phone-and-class": config_dict["norm-per-phone-and-class"],
                 "use-clipping":         	 config_dict["use-clipping"],
                 "batchnorm":            	 config_dict["batchnorm"],
				 "phones-file": 		 	 config_dict["phones-list-path"],
				 "labels-dir": 			 	 config_dict["labels-dir"],
				 "model-path": 			 	 config_dict["finetune-model-path"],
				 "phone-weights-path":   	 config_dict["phone-weights-path"],
				 "train-root-path": 		 config_dict["epadb-root-path"],
				 "test-root-path": 		     config_dict["heldout-root-path"],
				 "features-path": 		 	 config_dict["features-path"],
				 "conf-path": 			 	 config_dict["features-conf-path"],
				 "test-sample-list-dir": 	 config_dict["test-sample-list-dir"],
				 "state-dict-dir": 		 	 config_dict["state-dict-dir"],
				 "use-multi-process":    	 config_dict["use-multi-process"],
				 "device":               	 device_name				 
				}
	run_script("src/train.py", args_dict)


def run_evaluate_many_epochs(config_yaml, step=25):
	args_dict = {"config": config_yaml,
	             "step":   step
	            }
	run_script("evaluate_many_epochs.py", args_dict)

def run_all(config_yaml, stage, device_name, use_heldout):
	config_fh = open(config_yaml, "r")
	config_dict = yaml.safe_load(config_fh)	

	config_dict = extend_config_dict(config_yaml, config_dict, use_heldout)

	if stage in ["dataprep", "all"]:
		print("Running data preparation")
		run_data_prep(config_dict, 'exp')

	if stage in ["align", "all"]:
		print("Running aligner")
		run_align(config_dict)
	
	if stage in ["train+", "train", "all"]:
		if config_dict['use-kaldi-labels']:
			print("Creating Kaldi labels")
			run_create_kaldi_labels(config_dict, 'exp')
		print("Running training")
		run_train(config_dict, device_name)

	if stage in ["train+","evaluate", "all"]:
		print("Evaluating results")
		generate_scores_and_evaluate_epochs(config_dict, 25)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--config', dest='config_yaml',  help='Path .yaml config file for experiment', default=None)
	parser.add_argument('--stage', dest='stage',  help='Stage to run (dataprep, align, train, scores, evaluate), or \'all\' to run all stages', default=None)
	parser.add_argument('--device', dest='device_name', help='Device name to use, such as cpu or cuda', default=None)
	parser.add_argument('--heldout', action='store_true', help='Use this option to test on heldout set', default=False)

	args = parser.parse_args()
	use_heldout = args.heldout

	run_all(args.config_yaml, args.stage, args.device_name, use_heldout)
