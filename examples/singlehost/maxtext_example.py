"""Full parameter finetune a Gemma2 9B MaxText model on TPU or GPU.

This script should be run on multihost. 9B won't fit on single host. 

Singlehost: python3 examples/singlehost/maxtext_example.py 
Multihost:  python orchestration/multihost/ray/submit_ray_job.py "python3 examples/multihost/ray/TPU/maxtext_example_via_ray.py" --hf-token <TOKEN>
"""

import os
os.environ["KERAS_BACKEND"] = "jax"

import keras
from examples.example_datasets import example_datasets
from keras_tuner.model import MaxTextModel
from keras_tuner.dataset import Dataloader
from keras_tuner.preprocessor import PretrainingPreprocessor
from keras_tuner.trainer import Trainer
from typing import Union, Optional, List

import ray
#DO_NOT_SUBMIT
import subprocess
subprocess.run(["rm", "-rf", "/tmp/libtpu_lockfile", "/tmp/tpu_logs"])


config = {
    "hf_handle": "hf://google/gemma-2-9b",
    "seq_len": 100, #DO_NOT_SUBMIT change back to 4096
    "precision": "mixed_bfloat16",
    "training_steps": 100,
    "eval_steps_interval": 10,
    "log_steps_interval": 10,
    "per_device_batch_size": 1,
    "max_eval_samples": 50,
}


def run_workload(
    train_dataset: Union[ray.data.Dataset, List[str]], dataset_is_sharded_per_host: bool
):

    # Create Model
    model = MaxTextModel.from_preset(
        preset_handle=config["hf_handle"],
        seq_len=config["seq_len"],
        per_device_batch_size=config["per_device_batch_size"],
        precision=config["precision"],
    )

    import numpy as np

    input = {
        "tokens": np.array([[1,2,3,0,0,0]  for _ in range(128)]),
        "segment_ids": np.array([[1,1,1,0,0,0] for _ in range(128)]),
        "positions":np.array([[0,1,2,3,4,5]  for _ in range(128)]),
    }
    logits, non_trainable_variables = model.stateless_call(
        model.trainable_variables, model.non_trainable_variables, input
    )
    print("logits", logits[0])

    # Create Keras optimizer
    optimizer = keras.optimizers.AdamW(
        learning_rate=5e-5,
        weight_decay=0.01,
    )

    # Create Preprocessor
    preprocessor = PretrainingPreprocessor(
        tokenizer_handle=config["hf_handle"],
        seq_len=config["seq_len"],
        model_type="maxtext",
    )

    # Create Dataloader
    train_dataloader = Dataloader(
        train_dataset,
        per_device_batch_size=config["per_device_batch_size"],
        dataset_is_sharded_per_host=dataset_is_sharded_per_host,
    )

    # Initialize trainer
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        preprocessor=preprocessor,
        train_dataloader=train_dataloader,
        steps=10,
        log_steps_interval=1,
    )

    pred = trainer.generate(["What is your name?"]*16)
    print(f"before tuning model generated {pred}")
    # Start training
    trainer.train()

    pred = trainer.generate(["What is your name?"]*16)
    print(f"after tuning model generated {pred}")


if __name__ == "__main__":
    train_ds, eval_ds = example_datasets("finetune_toy")
    run_workload(
        train_ds,
        dataset_is_sharded_per_host=False,
    )
